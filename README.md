# Snapraid Runner Script

This script runs snapraid, and sends it output to the console, a log file and
via email. All this is configurable.

It can be run manually, but its main purpose is to be run via cronjob/windows
scheduler.

## How to use
* If you don’t already have it, download and install
  [the latest python 2.7](http://www.python.org/getit/).
* Download [the latest release](https://github.com/Chronial/snapraid-runner/releases)
  of this script and extract it anywhere or clone this repository via git.
* Copy/rename the `snapraid-runner.conf.example` to `snapraid-runner.conf` and
  edit its contents. You need to at least configure `snapraid.exectable` and
  `snapraid.config`.
* Run the script via `python snapraid-runner.py`.
* If you want to enable SMART monitoring on Windows or Mac OS, you must first
  download and install [smartmontools](https://www.smartmontools.org/wiki/Download).
  Most Linux distributions will have smartmontools installed by default.
  * Windows users may install using the packaged .exe installer found at this link or
    use [Chocolatey](https://chocolatey.org/) (i.e., `choco install smartmontools`).
  * Mac OS users may install using the packaged .dmg installer found at this link or
    use [Homebrew](https://brew.sh/) (i.e., `brew install smartmontools`).
  * Linux users may check for smartmontools using `smartctl -V`, if not installed use
    your distribution's package manager to install `smartmontools`
    (e.g., `apt-get install smartmontools`, `yum install smartmontools`, etc.)

## Features
* Runs `diff` before `sync` to see how many files were deleted and aborts if
  that number exceeds a set threshold.
* Can create a size-limited rotated logfile.
* Can send notification emails after each run or only for failures.
* Can run `scrub` after `sync`

## Changelog
### Unreleased
* Add support for running `snapraid touch` (by ShoGinn, PR-11)

### v0.3 (20 Jul 2017)
* Limit size of sent emails

### v0.2 (27 Apr 2015)
* Fix compatibility with Snapraid 8.0
* Allow disabling of scrub from command line

### v0.1 (16 Feb 2014)
* Initial release
