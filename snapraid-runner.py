# -*- coding: utf8 -*-
import argparse
import ConfigParser
import logging
import logging.handlers
import os.path
import subprocess
import sys
import threading
import traceback
from collections import Counter, defaultdict
from cStringIO import StringIO

# Global variables
config = None
email_log = None


def tee_log(infile, out_lines, log_level):
    """
    Create a thread thot saves all the output on infile to out_lines and
    logs every line with log_level
    """
    def tee_thread():
        for line in iter(infile.readline, ""):
            logging.log(log_level, line.strip())
            out_lines.append(line)
        infile.close()
    t = threading.Thread(target=tee_thread)
    t.daemon = True
    t.start()
    return t


def snapraid_command(command, args={}):
    """
    Run snapraid command
    Raises subprocess.CalledProcessError if errorlevel != 0
    """
    arguments = ["--conf", config["snapraid"]["config"]]
    for (k, v) in args.items():
        arguments.extend(["--" + k, str(v)])
    p = subprocess.Popen(
        [config["snapraid"]["executable"], command] + arguments,
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
    charset.add_charset("utf-8", charset.SHORTEST, charset.QP)
    if success:
        body = "SnapRAID job completed successfully:\n\n\n"
    else:
        body = "Error during SnapRAID job:\n\n\n"
    body += email_log.getvalue()
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = config["email"]["subject"] + \
        (" SUCCESS" if success else " ERROR")
    msg["From"] = config["email"]["from"]
    msg["To"] = config["email"]["to"]
    smtp = {"host": config["smtp"]["host"]}
    if config["smtp"]["port"]:
        smtp["port"] = config["smtp"]["port"]
    if config["smtp"]["ssl"]:
        server = smtplib.SMTP_SSL(**smtp)
    else:
        server = smtplib.SMTP(**smtp)
    if config["smtp"]["user"]:
        server.login(config["smtp"]["user"], config["smtp"]["password"])
    server.sendmail(
        config["email"]["from"],
        [config["email"]["to"]],
        msg.as_string())
    server.quit()


def finish(is_success):
    if ("error", "success")[is_success] in config["email"]["sendon"]:
        try:
            send_email(is_success)
        except:
            logging.exception("Failed to send email")
    if is_success:
        logging.info("Run finished successfully")
    else:
        logging.error("Run failed")
    sys.exit(0 if is_success else 1)


def load_config(file):
    global config
    parser = ConfigParser.RawConfigParser()
    parser.read(file)
    sections = ["snapraid", "logging", "email", "smtp", "scrub"]
    config = dict((x, defaultdict(lambda: "")) for x in sections)
    for section in parser.sections():
        for (k, v) in parser.items(section):
            config[section][k] = v.strip()

    int_options = [
        ("snapraid", "deletethreshold"), ("logging", "maxsize"),
        ("scrub", "percentage"), ("scrub", "older-than")
    ]
    for section, option in int_options:
        try:
            config[section][option] = int(config[section][option])
        except ValueError:
            config[section][option] = 0

    config["smtp"]["ssl"] = (config["smtp"]["ssl"].lower() == "true")
    config["scrub"]["enabled"] = (config["scrub"]["enabled"].lower() == "true")
    config["email"]["short"] = (config["email"]["short"].lower() == "true")


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

    if config["logging"]["file"]:
        max_log_size = min(config["logging"]["maxsize"], 0) * 1024
        file_logger = logging.handlers.RotatingFileHandler(
            config["logging"]["file"],
            maxBytes=max_log_size,
            backupCount=9)
        file_logger.setFormatter(log_format)
        root_logger.addHandler(file_logger)

    if config["email"]["sendon"]:
        global email_log
        email_log = StringIO()
        email_logger = logging.StreamHandler(email_log)
        email_logger.setFormatter(log_format)
        if config["email"]["short"]:
            # Don't send programm stdout in email
            email_logger.setLevel(logging.INFO)
        root_logger.addHandler(email_logger)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", nargs=1,
                        default="snapraid-runner.conf",
                        help="Configuration file (default %(default)s)")
    args = parser.parse_args()

    if not os.path.exists(args.conf):
        print("snapraid-runner configuration file not found")
        args.print_help()
        sys.exit(2)

    try:
        load_config(args.conf)
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
        run()
    except Exception:
        logging.exception("Run failed due to unexpected exception:")
        finish(False)


def run():
    logging.info("=" * 60)
    logging.info("Run started")
    logging.info("=" * 60)

    if not os.path.exists(config["snapraid"]["executable"]):
        logging.error("Snapraid executable does not exist at " +
                      config["snapraid"]["executable"])
        finish(False)
    if not os.path.exists(config["snapraid"]["config"]):
        logging.error("Snapraid config does not exist at " +
                      config["snapraid"]["config"])
        finish(False)

    logging.info("Running diff...")
    try:
        diff_out = snapraid_command("diff")
    except subprocess.CalledProcessError as e:
        logging.error(e)
        finish(False)
    logging.info("*" * 60)

    diff_results = Counter(line.split(" ")[0] for line in diff_out)
    diff_results = dict((x, diff_results[x]) for x in
                        ["add", "remove", "move", "update"])
    logging.info(("Diff results: {add} added,  {remove} removed,  "
                  + "{move} moved,  {update} modified").format(**diff_results))

    if (config["snapraid"]["deletethreshold"] >= 0 and
            diff_results["remove"] > config["snapraid"]["deletethreshold"]):
        logging.error(
            "Deleted files exceed delete threshold of {}, aborting".format(
            config["snapraid"]["deletethreshold"]))
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

    if config["scrub"]["enabled"]:
        logging.info("Running scrub...")
        try:
            snapraid_command("scrub", {
                "percentage": config["scrub"]["percentage"],
                "older-than": config["scrub"]["older-than"],
            })
        except subprocess.CalledProcessError as e:
            logging.error(e)
            finish(False)
        logging.info("*" * 60)

    logging.info("All done")
    finish(True)


main()
