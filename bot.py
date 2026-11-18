import argparse
import json
import logging
import re
import sys

import pywhatkit as kit


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def validate_phone(phone):
    phone = phone.strip()
    if not re.match(r"^\+\d{7,15}$", phone):
        raise ValueError(f"Invalid phone number: {phone}")
    return phone


def validate_time(hour, minute):
    if not (0 <= hour <= 23):
        raise ValueError(f"Hour must be 0-23, got {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Minute must be 0-59, got {minute}")


def send_one(phone, message, hour, minute, instant, wait_time, close_tab, close_time):
    if instant or hour is None or minute is None:
        kit.sendwhatmsg_instantly(
            phone, message, wait_time=wait_time, tab_close=close_tab, close_time=close_time
        )
    else:
        kit.sendwhatmsg(
            phone, message, hour, minute, wait_time=wait_time, tab_close=close_tab, close_time=close_time
        )
    logging.info("Message sent to %s", phone)


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_recipients(args, cfg):
    recipients = list(cfg.get("phones", [])) if cfg else []
    if args.phone:
        recipients.extend(args.phone)
    if args.recipients_file:
        with open(args.recipients_file, encoding="utf-8") as f:
            recipients.extend(line.strip() for line in f if line.strip())
    return recipients


def main():
    parser = argparse.ArgumentParser(description="WhatsApp message sender")
    parser.add_argument("-p", "--phone", action="append", help="recipient phone (with country code); repeatable")
    parser.add_argument("-m", "--message", help="message text")
    parser.add_argument("--hour", type=int, help="hour (24h)")
    parser.add_argument("--minute", type=int, help="minute")
    parser.add_argument("--instant", action="store_true", help="send immediately")
    parser.add_argument("--config", help="JSON config file")
    parser.add_argument("-f", "--recipients-file", help="file with one phone per line")
    parser.add_argument("--wait", type=int, default=15, help="wait time before sending")
    parser.add_argument("--close-time", type=int, default=3, help="seconds before closing tab")
    parser.add_argument("--no-close", action="store_true", help="keep tab open")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    cfg = load_config(args.config) if args.config else None

    message = args.message
    hour = args.hour
    minute = args.minute
    instant = args.instant

    if cfg:
        message = cfg.get("message", message)
        hour = cfg.get("hour", hour)
        minute = cfg.get("minute", minute)
        instant = cfg.get("instant", instant)

    recipients = collect_recipients(args, cfg)

    if not recipients:
        parser.error("no recipients provided (use --phone, --recipients-file, or config)")
    if not message:
        parser.error("no message provided")

    try:
        recipients = [validate_phone(r) for r in recipients]
    except ValueError as e:
        parser.error(str(e))

    if not instant:
        if hour is None or minute is None:
            parser.error("hour and minute required unless --instant")
        try:
            validate_time(hour, minute)
        except ValueError as e:
            parser.error(str(e))

    close_tab = not args.no_close
    failures = 0
    for r in recipients:
        try:
            send_one(r, message, hour, minute, instant, args.wait, close_tab, args.close_time)
        except Exception as e:
            logging.error("Failed to send to %s: %s", r, e)
            failures += 1

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
