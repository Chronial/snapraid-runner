# -*- coding: utf8 -*-
import ConfigParser
import argparse
import logging
import logging.handlers
import sys
import subprocess
import threading
import traceback
from collections import Counter
from cStringIO import StringIO


# TODO: check config validity
# TODO: alles in main und exceptions handlen
# finish() darf keine exceptions werfen!

# Global variables
config = None
email_log = None


def tee_log(infile, out_lines, log_level):
    def tee_thread():
        for line in iter(infile.readline, ''):
            logging.log(log_level, line.strip())
            out_lines.append(line)
        infile.close()
    t = threading.Thread(target=tee_thread)
    #t.daemon = True
    t.start()
    return t


def snapraid_command(command):
    p = subprocess.Popen(
        [config.get("snapraid", "executable"), command,
            "--conf", config.get("snapraid", "config")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out = []
    threads = [
        tee_log(p.stdout, out, logging.OUTPUT),
        tee_log(p.stderr, [], logging.OUTERR)]
    for t in threads:
        t.join()
    ret = p.wait()
    if ret == 0:
        return out
    else:
        raise subprocess.CalledProcessError(ret, "snapraid " + command)


def send_email(success):
    import smtplib
    from email.mime.text import MIMEText
    from email import charset
    # use quoted-printable instead of the default base64
    charset.add_charset('utf-8', charset.SHORTEST, charset.QP)
    if success:
        body = "SnapRAID job completed successfully:\n\n\n"
    else:
        body = "Error during SnapRAID job:\n\n\n"
    body += email_log.getvalue()
    msg = MIMEText(body, "plain", "utf-8")
    msg['Subject'] = config.get("email", "subject") + \
        " SUCCESS" if success else " ERROR"
    msg['From'] = config.get("email", "from")
    msg['To'] = config.get("email", "to")
    smtp = {"host": config.get("smtp", "host")}
    if config.get("smtp", "port"):
        smtp["port"] = config.getint("smtp", "port")
    if config.get("smtp", "ssl").lower() == "true":
        server = smtplib.SMTP_SSL(**smtp)
    else:
        server = smtplib.SMTP(**smtp)
    if config.get("smtp", "user"):
        server.login(config.get("smtp", "user"),
                     config.get("smtp", "password"))
    server.sendmail(
        config.get("email", "from"),
        [config.get("email", "to")],
        msg.as_string())
    server.quit


def finish(is_success):
    if is_success:
        logging.info("Run finished successfully")
    else:
        logging.error("Run failed")
    if ((is_success and "success" in config.get("email", "send")) or
            (not is_success and "error" in config.get("email", "send"))):
        send_email(is_success)
    sys.exit(0 if is_success else 1)


def load_config(file):
    global config
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.add_section("smtp")
    config.add_section("email")
    config.add_section("snapraid")
    config.set("snapraid", "delethreshold", 0)
    config.add_section("logging")
    config.set("logging", "file", None)
    config.set("logging", "maxsize", 0)
    config.read(file)


def setup_logger():
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)-6.6s] %(message)s")
    root_logger = logging.getLogger()
    logging.OUTPUT = 15
    logging.addLevelName(logging.OUTPUT, "OUTPUT")
    logging.OUTERR = 25
    logging.addLevelName(logging.OUTERR, "OUTERR")
    root_logger.setLevel(logging.OUTPUT)
    console_logger = logging.StreamHandler(sys.stdout)
    console_logger.setFormatter(log_format)
    root_logger.addHandler(console_logger)

    if config.get("logging", "file"):
        max_log_size = min(config.getint("logging", "maxsize"), 0) * 1024
        file_logger = logging.handlers.RotatingFileHandler(
            config.get("logging", "file"),
            maxBytes=max_log_size,
            backupCount=9)
        file_logger.setFormatter(log_format)
        root_logger.addHandler(file_logger)

    if config.get("email", "send"):
        global email_log
        email_log = StringIO()
        email_logger = logging.StreamHandler(email_log)
        email_logger.setFormatter(log_format)
        # Don't send programm stdout in email
        email_logger.setLevel(logging.INFO)
        root_logger.addHandler(email_logger)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--conf', nargs=1,
                        default='snapraid-runner.conf',
                        help='Configuration file (default %(default)s)')
    args = parser.parse_args()
    load_config(args.conf)
    setup_logger()

    logging.info("=" * 60)
    logging.info("Run started")
    logging.info("=" * 60)

    logging.info("Running diff...")
    try:
        diff_out = snapraid_command("diff")
    except subprocess.CalledProcessError as e:
        logging.error(e)
        finish(False)
    logging.info("*" * 60)

    diff_results = Counter(line.split(" ")[0] for line in diff_out)
    logging.info(("Diff results: {add} added,  {remove} removed,  "
                  + "{move} moved,  {update} modified").format(**diff_results))

    if (config.getint("snapraid", "deletethreshold") > 0 and
            diff_results["remove"] >
            config.getint("snapraid", "deletethreshold")):
        logging.error(
            "Deleted files exceed delete threshold {}, aborting".format(
            config.getint("snapraid", "deletethreshold")))
        finish(False)

    if (diff_results["remove"] + diff_results["add"] + diff_results["move"] +
            diff_results["update"] == 0):
        logging.info("No changes detected, no sync required")
        finish(True)

    logging.info("Running sync...")
    try:
        snapraid_command("sync")
    except subprocess.CalledProcessError as e:
        logging.error(e)
        finish(False)
    logging.info("*" * 60)

    logging.info("All done")
    finish(True)


try:
    load_config()
except:
    print("unexpected exception while loading config")
    print traceback.format_exc()
    sys.exit(2)

try:
    setup_logger()
except:
    print("unexpected exception while setting up logging")
    print traceback.format_exc()
    sys.exit(2)

try:
    main()
except Exception as e:
    logging.exception("Run failed due to unexpected exception:")
    finish(False)
