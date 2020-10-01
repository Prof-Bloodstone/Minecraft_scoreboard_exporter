#!/usr/bin/env python3
"""
Extracts top player scores from files written in NBT format.
Written by Prof_Bloodstone (aka B1o0dy) for use at Near Vanilla server.
"""
from __future__ import division

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from collections import namedtuple, defaultdict, ChainMap
from contextlib import contextmanager
from copy import deepcopy
from math import log

from nbt import nbt
from nbt.nbt import TAG_Short, StructError, TAG_String

if sys.version_info < (3, 5):
    try:
        from scandir import scandir
    except ImportError:
        DirEntry = namedtuple("DirEntry", ("path", "is_file"))

        def scandir(directory):
            paths = (
                os.path.join(directory, filename) for filename in os.listdir(directory)
            )
            return (DirEntry(path, lambda: os.path.isfile(path)) for path in paths)


else:
    from os import scandir

epsilon = sys.float_info.epsilon

PLAYER_SCORE = namedtuple("PLAYER_SCORE", ["name", "score"])
COMBINE_OBJ = namedtuple("COMBINE_OBJ", "regex, new_name")


# Sometimes the encoded strings seem to not be utf-8
# So we inject modified function which decodes them as latin-1
# Contents of this function are taken straight out of the NBT package
def _TAG_String_patched_parse_buffer(self, buffer):
    length = TAG_Short(buffer=buffer)
    read = buffer.read(length.value)
    if len(read) != length.value:
        raise StructError()
    self.value = read.decode("latin-1")

TAG_String._parse_buffer = _TAG_String_patched_parse_buffer


def extract_scores(nbtfile):
    """Extract scores from nbt file and convert to python format that is easier to work with."""
    objectives = {
        tag["Name"].value: {
            "DisplayName": json.loads(tag["DisplayName"].value)["text"],
            "scores": [],
        }
        for tag in nbtfile["data"]["Objectives"].tags
    }

    player_scores = nbtfile["data"]["PlayerScores"]

    for score in player_scores:
        player_name = score["Name"].value
        objective = score["Objective"].value
        value = score["Score"].value
        objectives[objective]["scores"].append(PLAYER_SCORE(player_name, value))

    return objectives


def combine_scores(objectives, to_combine, delete_combined=False):
    combined_objectives = defaultdict(lambda: defaultdict(int))
    to_delete = []
    for key, obj in objectives.items():
        new_name = next(
            (name for regex, name in to_combine if regex.search(key) is not None), None
        )
        if new_name is not None:
            to_delete.append(key)
            for player in obj["scores"]:
                combined_objectives[new_name][player.name] += player.score
    if delete_combined:
        for key in to_delete:
            del objectives[key]

    return {
        obj_name: {
            "DisplayName": obj_name,
            "scores": [
                PLAYER_SCORE(player_name, score) for player_name, score in obj.items()
            ],
        }
        for obj_name, obj in combined_objectives.items()
    }


def sort_scores(objectives, descending, reverse):
    for key, obj in objectives.items():
        sort_descending = descending if key not in reverse else not descending
        obj["scores"].sort(
            key=lambda x: (-x.score if sort_descending else x.score, x.name)
        )


def get_scores(
    from_file, combine, sort, reverse, number, whitelist, blacklist, delete_combined
):
    with create_temp(from_file) as file:
        objectives = extract_scores(file)

    combined_scores = combine_scores(objectives, combine, delete_combined)
    scores = dict(ChainMap(combined_scores, objectives))
    sort_scores(scores, sort, reverse)

    if number > 0:
        for key, obj in scores.items():
            scores[key]["scores"] = obj["scores"][:number]

    for key, obj in scores.items():
        scores[key]["scores"] = [
            {"index": index, "playerName": entry.name, "score": entry.score}
            for index, entry in enumerate(obj["scores"], start=1)
        ]

    return {
        key: value
        for key, value in scores.items()
        if key in combined_scores.keys()
        or key not in blacklist
        and (not whitelist or key in whitelist)
    }


def convert_scores(scores, convert):
    convert_dict = {
        "blocks": _convert_blocks,
        "si": _convert_si,
        "minutes": _convert_minutes,
        "seconds": _convert_seconds,
        "hours": _convert_hours,
        "hm": _convert_hm,
        "ms": _convert_ms,
        "hms": _convert_hms,
    }

    unit_dict = defaultdict(
        lambda: lambda x: x,
        {"t": lambda x: x, "cm": lambda x: x, "m": lambda x: x * 60 * 20,},
    )

    invalid_converts = {
        converter
        for converter in convert.keys()
        if (converter.split("_", maxsplit=1)[1] if "_" in converter else converter)
        not in convert_dict.keys()
    }
    if invalid_converts:
        print(
            "Following converters used are invalid:\n"
            "\t{}\n"
            "Available converters:\n"
            "\t{}".format(", ".join(invalid_converts), ", ".join(convert_dict.keys())),
            file=sys.stderr,
        )

    for ic in invalid_converts:
        del convert[ic]

    converted_scores = {}

    for converter, to_convert in convert.items():
        unit, conv_name = (
            converter.split("_", maxsplit=1) if "_" in converter else (None, converter)
        )

        if unit is None:
            print(
                "[{}] Unit type not given. Assuming default!".format(converter),
                file=sys.stderr,
            )
        elif unit not in unit_dict:
            print(
                '[{}] Invalid unit type "{}"! Using default!'.format(converter, unit),
                file=sys.stderr,
            )

        conv = convert_dict[conv_name]
        for score_name in to_convert:
            converted_scores[score_name] = deepcopy(scores[score_name])
            for entry in converted_scores[score_name]["scores"]:
                entry["score"] = conv(entry["score"])

    return dict(converted_scores)


def _convert_si(value):
    prefixes = ("", "K", "M", "G", "T", "P", "E", "Z", "Y", "OUT OF SI PREFIXES!")
    new_value = value / 10 ** (3 * int(log(value + epsilon, 1000)))
    prefix = prefixes[int(log(value + epsilon, 1000))]
    return "{:5.1f}{:1}".format(new_value, prefix)


def _convert_blocks(cm):
    return "{} blocks".format(_convert_si(cm / 100))


def _convert_minutes(ticks):
    sec = ticks // 20
    minutes = sec // 60
    return "{} minute{}".format(minutes, "s" if minutes != 1 else "")


def _convert_seconds(ticks):
    sec = ticks // 20
    return "{} second{}".format(sec, "s" if sec != 1 else "")


def _convert_hours(ticks):
    sec = ticks // 20
    hours = sec // 3600
    return "{} hour{}".format(hours, "s" if hours != 1 else "")


def _convert_hm(ticks):
    sec = ticks // 20
    minutes = (sec // 60) % 60
    hours = sec // 3600
    return "{} hour{} {} minute{}".format(
        hours, "s" if hours != 1 else "", minutes, "s" if minutes != 1 else ""
    )


def _convert_ms(ticks):
    sec = ticks // 20
    minutes = sec // 60
    return "{} minute{} {} second{}".format(
        minutes, "s" if minutes != 1 else "", sec, "s" if sec != 1 else ""
    )


def _convert_hms(ticks):
    sec = ticks // 20
    minutes = (sec // 60) % 60
    hours = sec // 3600
    return "{} hour{} {} minute{} {} second{}".format(
        hours,
        "s" if hours != 1 else "",
        minutes,
        "s" if minutes != 1 else "",
        sec,
        "s" if sec != 1 else "",
    )


def rchop(thestring, ending):
    """Chops the ending from string, if it matches."""
    if thestring.endswith(ending):
        return thestring[: -len(ending)]
    raise IOError('Invalid file found: "{}"'.format(thestring))


def get_UUID_with_names(playerdata_folder):
    UUID_name_pairs = []
    for file in (
        entry.path
        for entry in scandir(playerdata_folder)
        if entry.is_file() and entry.path.endswith(".dat")
    ):
        basename = os.path.basename(file)
        UUID = rchop(basename, ".dat")
        with create_temp(file) as nbtfile:
            playername = str(nbtfile["bukkit"]["lastKnownName"])
        UUID_name_pairs.append({"UUID": UUID, "lastKnownName": playername})
    return UUID_name_pairs


def extract_and_save_data(args):
    from_file = args["input_file"]
    to_file = args["output_file"]
    playerdata_folder = args["playerdata"]
    number = args["number"]
    combine = args["combine"]
    reverse = args["reverse"]
    sort = args["sort_descending"]
    whitelist = args["whitelist"]
    blacklist = args["blacklist"]
    delete_combined = args["delete_combined"]
    convert = args["convert"]

    scores = get_scores(
        from_file, combine, sort, reverse, number, whitelist, blacklist, delete_combined
    )
    converted_scores = convert_scores(scores, convert)

    output = {
        "timestamp": time.time(),
        "scores": dict(ChainMap(converted_scores, scores)),
    }

    if playerdata_folder is not None:
        output["UUID"] = get_UUID_with_names(playerdata_folder)

    with open(to_file, "w") as f:
        json.dump(output, f, sort_keys=True)


@contextmanager
def create_temp(file):
    """Copies and opens NBT file in read mode. Deletes it afterwards."""
    temp_dir = tempfile.gettempdir()
    basename = os.path.basename(file)
    temp_path = os.path.join(temp_dir, "{}.copy".format(basename))
    shutil.copyfile(file, temp_path)
    try:
        yield nbt.NBTFile(temp_path, "rb")
    finally:
        os.remove(temp_path)


def _parse_cli(defaults):
    arg_parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )

    arg_parser.add_argument(
        "-n",
        "--number",
        type=int,
        help="Number of scores to save.\n"
        "If <= 0, all scores will be saved"
        " [DEFAULT {}]".format(defaults["number"]),
    )

    arg_parser.add_argument(
        "-i",
        "--input",
        "--scoreboard",
        dest="input_file",
        type=str,
        help="Name of the file to read scores from [DEFAULT {}]".format(
            defaults["input_file"]
        ),
    )

    arg_parser.add_argument(
        "-t",
        "--output",
        "--top",
        dest="output_file",
        type=str,
        help="Name of the file to save scores to [DEFAULT {}]".format(
            defaults["output_file"]
        ),
    )

    arg_parser.add_argument(
        "-p",
        "--playerdata",
        type=str,
        help="Directory inside of which player data is stored, used to extract UUID and names.\n"
        "Need to be running Spigot/Bukkit for it to work!",
    )

    arg_parser.add_argument(
        "-a",
        "--ascending",
        action="store_false",
        help="Flag indicating that scoreboard should be sorted in ascending order by default",
    )

    arg_parser.add_argument(
        "-d",
        "--descending",
        action="store_true",
        help="Flag indicating that scoreboard should be sorted in descending order by default [DEFAULT]",
    )

    arg_parser.set_defaults(ascending=None, descending=None)

    arg_parser.add_argument(
        "-r",
        "--reverse",
        action="append",
        help="List of all objective names which should be sorted in the opposite direction to the"
        ' direction chosen by "ascending" / "descending" arguments.\n'
        "Has to be repeated for every item added!\n"
        'Example: "-r obj1 -r obj2 -r obj3"',
    )

    arg_parser.add_argument(
        "--combine",
        action="append",
        nargs=2,
        help="List of all objective names which should be combined into one.\n"
        'Have a form of regular expression and new name separated by a space "regex" "name"\n'
        "Has to be repeated for every item added!\n"
        'Example: "--combine distance total_traveled" will combine every scoreboard with name "distance" in them and save it into "total_traveled"',
    )

    arg_parser.add_argument(
        "--convert",
        action="append",
        nargs=2,
        help="List of all objective names which should be converted\n"
        'Have a form of converted name and score name separated by a space "blocks" "name"\n'
        "Has to be repeated for every item added!\n"
        'Example: "--convert blocks total_traveled" will convert scoreboard with name "total_traveled"',
    )

    arg_parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        type=str,
        help="File containing configuration. CLI arguments override it!",
    )

    arg_parser.add_argument(
        "-b",
        "--blacklist",
        action="append",
        help="List of all objective names which shouldn't be in the output file\n"
        "Has to be repeated for every item added!\n"
        'Example: "-b obj1 -b obj2 -b obj3"',
    )

    arg_parser.add_argument(
        "-w",
        "--whitelist",
        action="append",
        help="List of all objective names which should be in the output file\n"
        "Has to be repeated for every item added!\n"
        'Example: "-w obj1 -w obj2 -w obj3"',
    )

    arg_parser.add_argument(
        "--delete_combined",
        action="store_true",
        default=None,
        help="Flag indicating that source scoreboards used for combining should be deleted\n"
        "By default they don't get deleted",
    )

    return arg_parser.parse_args()


def parser():
    """Take care of parsing arguments from CLI and config file, if provided."""

    defaults = {
        "number": 0,
        "input_file": "scoreboard.dat",
        "output_file": "top_scores.json",
        "sort_descending": True,
        "reverse": [],
        "combine": [],
        "blacklist": [],
        "whitelist": [],
        "convert": {},
        "delete_combined": False,
    }

    cli_args = _parse_cli(defaults)

    if None not in (cli_args.ascending, cli_args.descending):
        raise argparse.ArgumentError(
            'Can\'t provide both "ascending" and "descending" arguments!'
        )

    cli_args.sort_descending = next(
        item
        for item in (
            cli_args.ascending,
            cli_args.descending,
            defaults["sort_descending"],
        )
        if item is not None
    )

    if cli_args.convert is not None:
        convert = defaultdict(list)
        for key, value in cli_args.convert:
            convert[key].append(value)
        cli_args.convert = convert

    config_args = {}

    if cli_args.config_file is not None:
        if cli_args.config_file != "-":
            with open(cli_args.config_file, "r") as f:
                config_args = json.load(f)
        else:
            config_args = json.load(sys.stdin)

        if config_args.get("combine") is not None:
            config_args["combine"] = [
                COMBINE_OBJ(re.compile(item["regex"]), item["new_name"])
                for item in config_args["combine"]
            ]

        del cli_args.config_file

    if cli_args.combine is not None:
        cli_args.combine = [
            COMBINE_OBJ(re.compile(regex), name) for regex, name in cli_args.combine
        ]

    cli_args_dict = {
        key: value for key, value in vars(cli_args).items() if value is not None
    }

    # TODO translate config names to accept the same as CLI

    return ChainMap({}, cli_args_dict, config_args, defaults, defaultdict(lambda: None))


def main():
    args = parser()

    tries = 3
    while tries > 0:
        try:
            extract_and_save_data(args)
        except Exception as e:
            tries -= 1
            if tries <= 0:
                return 1
            print(
                "Exception {} occured. Trying again {} more time{}.\n{}".format(
                    type(e).__name__,
                    tries,
                    "s" if tries != 1 else "",
                    traceback.format_exc(),
                ),
                file=sys.stderr,
            )
        else:
            tries = 0

    return 0


if __name__ == "__main__":
    exit(main())
