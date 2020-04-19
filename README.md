# Snapraid Runner Script

This script runs snapraid and sends its output to the console, a log file and
via email. All this is configurable.

It can be run manually, but its main purpose is to be run via cronjob/windows
scheduler.

It supports Windows, Linux and macOS and runs on both python2 and python3.

## How to use
* If you don’t already have it, download and install
  [the latest python version](https://www.python.org/downloads/).
* Download [the latest release](https://github.com/Chronial/snapraid-runner/releases)
  of this script and extract it anywhere or clone this repository via git.
* Copy/rename the `snapraid-runner.conf.example` to `snapraid-runner.conf` and
  edit its contents. You need to at least configure `snapraid.executable` and
  `snapraid.config`.
* Run the script via `python3 snapraid-runner.py` on Linux or
 `py -3 snapraid-runner.py` on Windows.

## Features
* Runs `diff` before `sync` to see how many files were deleted and aborts if
  that number exceeds a set threshold.
* Can create a size-limited rotated logfile.
* Can send notification emails after each run or only for failures.
* Can run `scrub` after `sync`

## Changelog
### Unreleased
* Fix snapraid output encoding handling  (by hyyz17200, PR-31)

### v0.4 (17 Aug 2019)
* Add compatibility with python3 (by reed-jones)
* Add support for running `snapraid touch` (by ShoGinn, PR-11)
* Add SMTP TLS support

### v0.3 (20 Jul 2017)
* Limit size of sent emails

### v0.2 (27 Apr 2015)
* Fix compatibility with Snapraid 8.0
* Allow disabling of scrub from command line

### v0.1 (16 Feb 2014)
* Initial release
