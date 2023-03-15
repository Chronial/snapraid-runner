#!/usr/bin/env python3

from argparse import ArgumentParser
# noinspection PyUnresolvedReferences, PyProtectedMember
from configparser import RawConfigParser, _UNSET
import logging
from logging.handlers import RotatingFileHandler
import os.path
import subprocess
import sys
from threading import Thread
import time
from collections import Counter
from io import StringIO


class RunnerConfigParser(RawConfigParser):
    def getstring(self, section, option, *, fallback=_UNSET):
        # noinspection PyProtectedMember
        value = super()._get_conv(section, option, str, fallback=fallback)
        if value is None:
            return value
        value = value.strip()
        if len(value) == 0:
            if fallback is _UNSET:
                raise ValueError('Option "%s" in section "%s" cannot be an empty string.'
                                 % (option, section))
            return fallback
        return value


def tee_log(infile, log_level):
    """
    Create a thread that saves all the output on infile to out_lines and
    logs every line with log_level
    """
    out_lines = []

    def tee_thread():
        for line in iter(infile.readline, ''):
            logging.log(log_level, line.rstrip())
            out_lines.append(line)
        infile.close()

    t = Thread(target=tee_thread)
    t.daemon = True
    t.start()
    return t, out_lines


class SnapraidRunner:
    OUTPUT = 15
    OUTERR = 25

    def __init__(self, config_file, scrub=True, ignore_deletethreshold=False, dry_run=False):
        self.dry_run = dry_run

        if not os.path.exists(config_file):
            raise ValueError('Configuration file does not exist.')

        config = RunnerConfigParser()
        config.read(config_file)

        # SnapRaid Options
        self.snapraid_exe = config.getstring('snapraid', 'executable')
        self.snapraid_config = config.getstring('snapraid', 'config')
        self.delete_threshold = config.getint('snapraid', 'deletethreshold', fallback=0)
        if ignore_deletethreshold:
            self.delete_threshold = -1
        self.snapraid_touch = config.getboolean('snapraid', 'touch', fallback=False)

        # Logging Options
        self.log_maxsize = config.getint('logging', 'maxsize', fallback=0)
        self.log_file = config.getstring('logging', 'file', fallback=None)

        # Scrub Options
        self.scrub_older_than = config.getint('scrub', 'older-than', fallback=None)
        self.scrub_enabled = scrub if scrub is not None else \
            config.getboolean('scrub', 'enabled', fallback=False)
        self.scrub_plan = config.getstring('scrub', 'plan', fallback=None)
        scrub_percentage = config.getint('scrub', 'percentage', fallback=None)
        if scrub_percentage is not None:
            self.scrub_plan = scrub_percentage

        # Email Options
        self.email_maxsize = config.getint('email', 'maxsize', fallback=500)
        self.email_short = config.getboolean('email', 'short', fallback=False)
        self.email_subject = config.getstring('email', 'subject', fallback=None)
        self.email_to = config.getstring('email', 'to', fallback=None)
        self.email_from = config.getstring('email', 'from', fallback=None)
        self.email_sendon = config.getstring('email', 'sendon', fallback=None)
        if self.email_sendon is not None:
            self.email_sendon = self.email_sendon.split(',')

        # SMTP Options
        self.smtp_ssl = config.getboolean('smtp', 'ssl', fallback=False)
        self.smtp_tls = config.getboolean('smtp', 'tls', fallback=False)
        self.smtp_host = config.getstring('smtp', 'host', fallback=None)
        self.smtp_port = config.getstring('smtp', 'port', fallback=None)
        self.smtp_user = config.getstring('smtp', 'user', fallback=None)
        self.smtp_password = config.getstring('smtp', 'password', fallback=None)

        # Global Variables
        self.email_stream = None
        self.logger = None

    def snapraid_command(self, command, allow_statuscodes=None, **kwargs):
        cli_args = ['--conf', self.snapraid_config, '--quiet']
        for k, v in kwargs.items():
            cli_args.extend(['--' + k, str(v)])

        if self.dry_run:
            logging.info(' '.join([self.snapraid_exe, command] + cli_args))
            return []

        p = subprocess.Popen(
            [self.snapraid_exe, command] + cli_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Snapraid always outputs utf-8 on windows. On linux, utf-8
            # also seems a sensible assumption.
            encoding='utf-8',
            errors='replace'
        )

        stdout, out_lines = tee_log(p.stdout, self.OUTPUT)
        stderr, _ = tee_log(p.stderr, self.OUTERR)
        for t in [stdout, stderr]:
            t.join()

        return_code = p.wait()
        # sleep for a while to prevent output mixup
        time.sleep(0.3)
        if return_code != 0:
            if allow_statuscodes is None or return_code not in allow_statuscodes:
                raise subprocess.CalledProcessError(return_code, 'snapraid ' + command)

        return out_lines

    def create_logger(self):
        log_format = logging.Formatter('%(asctime)s [%(levelname)-6.6s] %(message)s')
        logging.addLevelName(self.OUTPUT, 'OUTPUT')
        logging.addLevelName(self.OUTERR, 'OUTERR')
        logger = logging.getLogger()
        logger.setLevel(self.OUTPUT)

        console_logger = logging.StreamHandler(sys.stdout)
        console_logger.setFormatter(log_format)
        logger.addHandler(console_logger)

        if self.log_file:
            max_log_size = max(self.log_maxsize, 0) * 1024
            file_logger = RotatingFileHandler(
                self.log_file,
                maxBytes=max_log_size,
                backupCount=9
            )
            file_logger.setFormatter(log_format)
            logger.addHandler(file_logger)

        if self.email_sendon is not None:
            self.email_stream = StringIO()
            email_logger = logging.StreamHandler(self.email_stream)
            email_logger.setFormatter(log_format)
            if self.email_short:
                # Don't send programm stdout in email
                email_logger.setLevel(logging.INFO)
            logger.addHandler(email_logger)

    def send_email(self, success):
        import smtplib
        from email.mime.text import MIMEText
        from email import charset

        for varname in ['smtp_host', 'email_subject', 'email_to', 'email_from']:
            if getattr(self, varname) is None:
                logging.error('Failed to send email because option "%s" is not set' % varname)
                return

        # use quoted-printable instead of the default base64
        charset.add_charset('utf-8', charset.SHORTEST, charset.QP)
        if success:
            body = 'SnapRAID job completed successfully:\n\n\n'
        else:
            body = 'Error during SnapRAID job:\n\n\n'

        log = self.email_stream.getvalue()
        maxsize = self.email_maxsize * 1024
        if maxsize and len(log) > maxsize:
            cut_lines = log.count('\n', maxsize // 2, -maxsize // 2)
            log = (
                'NOTE: Log was too big for email and was shortened\n\n' +
                log[:maxsize // 2] +
                '[...]\n\n\n --- LOG WAS TOO BIG - {} LINES REMOVED --\n\n\n[...]'.format(cut_lines) +
                log[-maxsize // 2:]
            )
        body += log

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = self.email_subject + (' SUCCESS' if success else ' ERROR')
        msg['From'] = self.email_from
        msg['To'] = self.email_to
        smtp = {'host': self.smtp_host}
        if self.smtp_port is not None:
            smtp['port'] = self.smtp_port
        if self.smtp_ssl:
            server = smtplib.SMTP_SSL(**smtp)
        else:
            server = smtplib.SMTP(**smtp)
            if self.smtp_tls:
                server.starttls()
        if self.smtp_user:
            server.login(self.smtp_user, '' if self.smtp_password is None else self.smtp_password)
        server.sendmail(self.email_from, [self.email_to], msg.as_string())
        server.quit()

    def run(self):
        logging.info('=' * 60)
        logging.info('Run started')
        logging.info('=' * 60)

        if not os.path.isfile(self.snapraid_exe):
            logging.error('The configured snapraid executable "%s" does not '
                          'exist or is not a file' % self.snapraid_exe)
            self.finish(False)
        if not os.path.isfile(self.snapraid_config):
            logging.error('Snapraid config "%s" does not exist or is not a file.' % self.snapraid_config)
            self.finish(False)

        if self.snapraid_touch:
            logging.info('Running touch...')
            self.snapraid_command('touch')
            logging.info('*' * 60)

        logging.info('Running diff...')
        diff_out = self.snapraid_command('diff', allow_statuscodes=[2])
        logging.info('*' * 60)

        diff_results = Counter(line.split(' ')[0] for line in diff_out)
        diff_results = {x: diff_results[x] for x in ['add', 'remove', 'move', 'update']}
        logging.info(('Diff results: {add} added, {remove} removed, ' +
                      '{move} moved, {update} modified').format(**diff_results))

        if 0 <= self.delete_threshold < diff_results['remove']:
            logging.error('Deleted files exceed delete threshold of %d, aborting'
                          % self.delete_threshold)
            logging.error('Run again with --ignore-deletethreshold to sync anyways')
            self.finish(False)

        if sum([diff_results[x] for x in ['remove', 'add', 'move', 'update']]) == 0:
            logging.info('No changes detected, no sync required')
        else:
            logging.info('Running sync...')
            try:
                self.snapraid_command('sync')
            except subprocess.CalledProcessError as e:
                logging.error(e)
                self.finish(False)
            logging.info('*' * 60)

        if self.scrub_enabled:
            logging.info('Running scrub...')
            scrub_args = {}
            if self.scrub_plan is not None:
                try:
                    self.scrub_plan = int(self.scrub_plan) # Check if a percentage plan was given
                except ValueError:
                    pass
            scrub_args.update({'plan': self.scrub_plan})
            if self.scrub_plan is None or isinstance(self.scrub_plan, int):
                scrub_args.update({'older-than': self.scrub_older_than})
            try:
                self.snapraid_command('scrub', **scrub_args)
            except subprocess.CalledProcessError as e:
                logging.error(e)
                self.finish(False)
            logging.info('*' * 60)

        logging.info('All done')
        self.finish(True)

    def finish(self, is_success):
        status = ('error', 'success')[is_success]
        if self.email_sendon is not None and status in self.email_sendon:
            try:
                self.send_email(is_success)
            except Exception:
                logging.exception('Failed to send email')
        if is_success:
            logging.info('Run finished successfully')
        else:
            logging.error('Run failed')
        sys.exit(0 if is_success else 1)


def main():
    parser = ArgumentParser()
    parser.add_argument('-c', '--conf',
                        default='snapraid-runner.conf',
                        dest='config_file',
                        metavar='CONFIG',
                        help='Configuration file (default: %(default)s)')
    parser.add_argument('--no-scrub', action='store_false',
                        dest='scrub', default=None,
                        help='Do not scrub (overrides config)')
    parser.add_argument('--ignore-deletethreshold', action='store_true', default=False,
                        help='Sync even if configured delete threshold is exceeded')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='Display commands but do not run them')
    args = parser.parse_args()

    try:
        runner = SnapraidRunner(**vars(args))
    except Exception as e:
        raise Exception('Unexpected exception while loading config.')\
            .with_traceback(e.__traceback__)

    try:
        runner.create_logger()
    except Exception as e:
        raise Exception('Unexpected exception while setting up logging')\
            .with_traceback(e.__traceback__)

    try:
        runner.run()
    except Exception:
        logging.exception('Run failed due to unexpected exception:')
        runner.finish(False)


main()
