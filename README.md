# Snapraid Runner Script - Yagmail Fork

This script runs snapraid and sends its output to the console, a log file and
via email. All this is configurable.

It can be run manually, but its main purpose is to be run via cronjob/windows
scheduler.

It supports Windows, Linux and macOS and requires at least python3.7.

**This is a fork** of the original script that supports sending from new **gmail accounts that can't enable smtp access**. Yagmail is used to authenticate via oauth2, this requires some manual setup of the sending account and of the oauth2 credentials on the first run of the script.

[This](https://blog.macuyiko.com/post/2016/how-to-send-html-mails-with-oauth2-and-gmail-in-python.html) shows how to setup your sending google account via the Google API Console. And [This](https://github.com/kootenpv/yagmail#oauth2) walks through the prompts that the console will ask about on the first run.

This fork also adds an optional check on the number of modified files to abort if it is over a configurable threshold, this is a rudimentary method of stopping some ransomware. **This is a very poor method of ransomeware detection and mitigation**, offline and or immutable backups are highly suggested.

## How to use
* If you don’t already have it, download and install
  [the latest python version](https://www.python.org/downloads/).
* Install yagmail via pip if you are planning on using it
* Download [the latest release](https://github.com/AndyHegemann/snapraid-runner/releases)
  of this script and extract it anywhere or clone this repository via git.
* Copy/rename the `snapraid-runner.conf.example` to `snapraid-runner.conf` and
  edit its contents. You need to at least configure `snapraid.executable` and
  `snapraid.config`.
* Run the script via `python3 snapraid-runner.py` on Linux or
 `py -3 snapraid-runner.py` on Windows.

## Features
* Runs `diff` before `sync` to see how many files were deleted and or modified and aborts if
  that number exceeds a set threshold.
* Can create a size-limited rotated logfile.
* Can send notification emails after each run or only for failures.
  * Can attach log after each run or only for failures
* Can run `scrub` after `sync`

## Scope of this project and contributions
~Snapraid-runner is supposed to be a small tool with clear focus. It should not
have any dependencies to keep installation trivial. I always welcome bugfixes
and contributions, but be aware that I will not merge new features that I feel
do not fit the core purpose of this tool.~

~I keep the PRs for features I do not plan on merging open, so if there's a
feature you are missing, you can have a look
[at the open PRs](https://github.com/Chronial/snapraid-runner/pulls).~

I added features to the original that I wanted, please feel free to do the same to my fork. There is a very good chance I broke something, but if I'm not going to use it then I probably won't get around to fix it. PRs for fixes and features will probably get merged if you feel like opening one.

## Changelog

### vA0.6 (24 Jul 2022)
* Add Yagmail (oauth2) support
* Add attaching log file to email report
  * Add attach log file only on error
* Add abort on too many modified files
* Add --ignore-modifythreshold

### Unreleased
* Add --ignore-deletethreshold (by exterrestris, #25)
* Add support for scrub --plan, replacing --percentage (thanks to fmoledina)
* Remove snapraid progress output. Was accidentially introduced with python3
  support.

### v0.5 (26 Feb 2021)
* Remove (broken) python2 support
* Fix snapraid output encoding handling (by hyyz17200, #31)
* Fix log rotation (by ptoulouse, #36)

### v0.4 (17 Aug 2019)
* Add compatibility with python3 (by reed-jones)
* Add support for running `snapraid touch` (by ShoGinn, #11)
* Add SMTP TLS support

### v0.3 (20 Jul 2017)
* Limit size of sent emails

### v0.2 (27 Apr 2015)
* Fix compatibility with Snapraid 8.0
* Allow disabling of scrub from command line

### v0.1 (16 Feb 2014)
* Initial release
