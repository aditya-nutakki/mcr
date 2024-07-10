import os, json
import re
import random
import requests


"""
    This utils file is strictly for pythonic functions with native libraries,
    embedding_utils file is where utils for third-party library exist
"""


def write_json(data, filepath, mode = "w"):
    with open(filepath, mode) as f:
        json.dump(data, f)


def read_json(path):
    with open(path, 'r') as f:
      data = json.load(f)
    return data


def write_jsonl(data, filepath, mode = "w"):

    assert filepath.endswith("jsonl"), f"use .jsonl as extension in your filepath for this function"

    # Write data to the JSONL file
    with open(filepath, mode) as f:
        for item in data:
            json.dump(item, f)  # Write JSON object
            f.write('\n')  # Add newline character after each JSON object


def write_txt(data, path):
    with open(path, 'w') as file:
        # Write each element of the list followed by a newline character
        for item in data:
            file.write(f"{item}\n")


def write_txt_dump(data, path):
    with open(path, 'w') as file:
        file.write(data)


def read_txt(path):
    """
    reads a txt file, assumes last line as source and the rest as content
    """

    with open(path, "r") as f:
        data = f.readlines()
        for i in range(len(data)):
            data[i] = data[i].strip()
            
    return "".join(data[:-1]).split("."), data[-1]


def read_txt_v2(path):
    """
    reads a txt file, returns the content as a single sentence
    """

    with open(path, "r") as f:
        data = f.readlines()
        for i in range(len(data)):
            data[i] = data[i].strip()
            
    return ".".join(data)



def split_jsonl(input_file, test_set_split = 0.2):

    assert input_file.endswith(".jsonl"), f"expected file with .jsonl extension and not {input_file}"

    with open(input_file, 'r') as infile:
        data = infile.readlines()

    total_lines = len(data)
    sample_size = int(test_set_split * total_lines)

    # Randomly select 20% of the lines
    random_sample = random.sample(data, sample_size)

    _save_path = input_file[:-6]
    print(input_file)
    print(_save_path)
    # Save the 20% to one file
    with open(f"{_save_path}_{str(test_set_split)}.jsonl", 'w') as test_outfile:
        test_outfile.writelines(random_sample)

    # Save the remaining 80% to another file
    remaining_80 = [line for line in data if line not in random_sample]
    with open(f"{_save_path}_{str(1 - test_set_split)}.jsonl", 'w') as train_outfile:
        train_outfile.writelines(remaining_80)


def remove_unicode_escape_sequences(input_string):
    pattern = r'(\\u0[0-9a-fA-F]{1,2})|(\\x[0-9a-fA-F]{1,2})|\xa0'
    cleaned_string = re.sub(pattern, '', input_string)
    return cleaned_string


def parse_steps_stream(text):
    pattern = r'\d+\.\s'
    sections = re.split(pattern, text)
    
    # Remove any empty strings from the resulting list (caused by the split at the start of the text)
    sections = [section for section in sections if section.strip()]
    return sections


def extract_links(response_message):
    # Regular expression to extract URLs from text    
    pattern = r'https?://[^\s>]+'
    matches = re.findall(pattern, response_message)
    print("Extracted URLs:", matches)
    return matches


def remove_html_tags(text):
    # regex to remove anything in between html tags. ie between <xyz> and </xyz>
    clean_text = re.sub(r'</?[^>]+>', '', text)
    return clean_text


def analyse_stream(word_stream, stream_def, look_for_defs, current_behaviour, found_closing_tag = False):

    for _def in look_for_defs:
        if _def in word_stream:
            found_def = re.search(_def, word_stream)
            if found_def and not found_closing_tag:
                x, y = found_def.span()
                closing_tag = stream_def[_def]["closing_tag"]
                behaviour = stream_def[_def]["behaviour"]

                return {
                    "indices": [x, y],
                    "closing_tag": closing_tag,
                    "behaviour": behaviour
                   }

            elif found_def and found_closing_tag:
                # print(f"found {_def}")
                # what happens when you find the closing tag
                x, y = found_def.span()
                return {
                    "indices": [x, y],
                    "closing_tag": "",
                    "behaviour": current_behaviour
                   }

    return {}


def process_analysis(analysis, stream_def, return_behaviour = False):
    x, y = analysis["indices"]
    closing_tag = analysis["closing_tag"]

    found_closing_tag = True if closing_tag else False # can be renamed to more like -> need_to_find_closing_tag
    look_for_defs = [closing_tag] if found_closing_tag else list(stream_def.keys())
    behaviour = analysis["behaviour"]

    return (x, y, closing_tag, found_closing_tag, look_for_defs, behaviour) if return_behaviour else (x, y, closing_tag, found_closing_tag, look_for_defs)
