import os, json
import sys
from dotenv import load_dotenv
from time import sleep
import re
from script_utils import *
from json_repair import repair_json
import uuid
load_dotenv()

# meant to be run as a standalone file after cd'ing into this dir
sys.path.append("../")

from modules import *
from bundles import *
from random import random, choice


# all save paths and file paths must be full paths UNLESS you will be manipulating something relative to a directory

save_dir = "/mnt/d/work/projects/agents/scripts/processed_data"
os.makedirs(save_dir, exist_ok = True)

# tracker_path = "./tracker_set_3020.json"
tracker_path = "./tracker_set_16110.json"
if os.path.exists(tracker_path):
    tracker = read_json(tracker_path)
else:
    tracker = {"visited": [], "processed": [], "failed": [], "processed_not_converted": []}
    write_json(data = tracker, filepath = tracker_path)


sonnet_chance = 0.1

judegments_path = "/mnt/d/work/datasets/scr2/"


"""
structure for tracker is as follows:

{
"processed": [{src_path: "file1.pdf", "save_path": "file2.pdf"}, ...],
"failed": ["file32.pdf", "file92.pdf", ...], # a list that contains all files (src_path) that have failed for whatever reason; internet connection drop, API fail on their end etc
"processed_not_converted": [{src_path: "file7.pdf", "save_path": "file7.txt"} ...] # contains a dict of where it was saved and where its source is; save all non-converted things into a txt file
"visited": ["file1.pdf", "file7.pdf", "file92.pdf", ...] # this contains a list of everyfile that has been touched. 
}

"""


def remove_double_n(text):
    pattern = r'\n{2,}'
    return re.sub(pattern, '', text)


class Indexer(BaseClaudeAgent):
    def __init__(self, bundle):
        super().__init__(bundle = bundle)

    
    def raw_call(self, file_data, **kwargs):
        
        context = [{"role": "user", "content": file_data}, {"role": "assistant", "content": "{"}] # speak for claude
        model = "claude-3-haiku-20240307" if random() > sonnet_chance else "claude-3-5-sonnet-20240620"

        try:
            if kwargs:
                response = self._process_call(context = context, model = model, **kwargs)
            else:
                response = self._process_call(context = context, model = model)
            return response
    
        except Exception as e:
            print(f"Failed because {e}")
            return ""



    def __call__(self, file_path, tracker, mode = "index"):
        print(f"doing {file_path}; tracker: {tracker}; mode: {mode}")
        if mode != "re-index":
            if file_path in tracker["visited"]:
                return
        
        file_name = file_path.split("/")[-1]

        try:
            file_data = remove_double_n(parse_file(file_path))
        except Exception as e:
            print(f"failed parsing {file_path}; because {e}; continuing")
            if mode != "re-index":
                tracker["failed"].append(file_path)
                tracker["visited"].append(file_path)
            
            return
            
        
        response = self.raw_call(file_data = file_data)

        if response:
            response = "{" + response # since using speak for claude

        else:
            sleep_time = 1.5 if mode == "re-index" else 8
            print(f"failed processing call for {file_path}; because {e}; continuing")
            if mode != "re-index":
                tracker["failed"].append(file_path)
                tracker["visited"].append(file_path)
                
            print(f"Failed mostly due to API error sleeping for {sleep_time} seconds")
            sleep(sleep_time)
            return
        

        try:    
            save_path = os.path.join(save_dir, file_name.replace(".pdf", ".json"))
            response = json.loads(response)
            write_json(data = response, filepath = save_path)
            tracker["processed"].append({
                "src_path": file_path,
                "save_path": save_path
            })

            if mode == "re-index":
                tracker["failed"].remove(file_path)


        except Exception as e:
            print(f"failed converting response into JSON for {file_path}; because {e}; continuing")
            save_path = os.path.join(save_dir, file_name.replace(".pdf", ".txt"))
            write_txt_dump(data = response, path = save_path)
            tracker["processed_not_converted"].append({
                "src_path": file_path,
                "save_path": save_path
            })

            if mode == "re-index":
                tracker["failed"].remove(file_path)


        finally:
            if (mode == "re-index") and file_path in tracker["visited"]:
                return
            tracker["visited"].append(file_path)
            return


indexer = Indexer(bundle = claude_extraction_bundle_v2)

def index_judegments():
    scrs = [os.path.join(judegments_path, judgement_path) for judgement_path in os.listdir(judegments_path)]

    num_concurrent = 5
    offset = 0 
    for i in range(0, len(scrs), num_concurrent):

        if i < offset:
            continue

        files = scrs[i: i + num_concurrent]
        print(f"{files}; set {i}")
        
        with ThreadPoolExecutor(max_workers=16) as executor:
            indexer_with_mode = partial(indexer, mode = "index")
            search_results = list(executor.map(indexer_with_mode, files))

        write_json(data = tracker, filepath = tracker_path)
        print("---------------")
        sleep(1.5) # sleep 1 seconds in between to stop from accidentally going into "visited" 
        print()



def review_failed():
    failed_judgements = tracker["failed"]
    print(len(failed_judgements))
    

    num_concurrent = 5
    offset = -1 # you must be careful while using offset and then re-running the same function as it there is popping function here

    for i in range(0, len(failed_judgements), num_concurrent):
        if i < offset:
            continue

        files = failed_judgements[i: i + num_concurrent]
        print(f"{files}; set {i}")
        
        with ThreadPoolExecutor(max_workers=16) as executor:
            # search_results = list(executor.map(pplx_search, steps))
            # search_results = list(executor.map(indexer, files, "re-index"))
            indexer_with_mode = partial(indexer, mode = "re-index")
            search_results = list(executor.map(indexer_with_mode, files))

        write_json(data = tracker, filepath = tracker_path)
        print("---------------")
        sleep(1.5) # sleep 1 seconds in between to stop from accidentally going into "visited" 
        print()



def _pop_from_tracker(tracker, val):
    processed_not_converted = tracker["processed_not_converted"]
    # print(val)
    for i, x in enumerate(processed_not_converted):
        original_save_path = x["save_path"]
        
        original_save_path = os.path.join("/".join(val.split("/")[:-1]), original_save_path.split("/")[-1]) # this was done only because there were some paths which had the save_path as a relative path and not an absolute path. make sure it is always absolute to avoid confusion

        if original_save_path == val:
            src_path = x["src_path"]
            processed_not_converted.pop(i)
            break
    
    tracker["processed"].append({
        "src_path": src_path,
        "save_path": val.replace(".txt", ".json")
    })



def convert_txt_to_jsons(path = "/mnt/d/work/projects/agents/scripts/processed_data", tracker_path = ""):
    indexed_files = [os.path.join(path, file) for file in os.listdir(path)]
    tracker = read_json(tracker_path)
    
    done_count, count = 0, 0
    for i, processed_file in enumerate(indexed_files):
        if processed_file.endswith(".txt"):

            data_string = open(processed_file, "r").read()
            json_string = get_brackets(data_string)
            # print(processed_file, opening_idx, closing_idx)
            _save_path = os.path.join(path, processed_file.split("/")[-1].replace(".txt", ".json")) # in place overwriting
            
            try:
                _json = json.loads(json_string)

                write_json(data = _json, filepath = _save_path)
                os.remove(processed_file)
                done_count += 1
                print(f"saved at {_save_path}; {i}")

                # Dont forget to pop from the tracker file
                _pop_from_tracker(tracker, val = processed_file)

            except Exception as e:
                # print(f"failed {processed_file}; {i}; {e}")
                try:
                    fixed_string = repair_json(json_string)
                    # If the string was super broken this will return an empty string - meaning a literaly double quotes as a string-> as per official documentation https://github.com/mangiucugna/json_repair?tab=readme-ov-file
                    # print(fixed_string, len(fixed_string), repr(fixed_string), type(fixed_string))

                    if fixed_string and fixed_string != '""':
                        _json = json.loads(fixed_string)
                        write_json(data = _json, filepath = _save_path)
                        os.remove(processed_file)
                        done_count += 1
                        
                        _pop_from_tracker(tracker, val = processed_file)
                        print(f"saved busted json at {_save_path}; {i}")

                    else:
                        print(f"Failed to repair json; {processed_file}; {i}; {e}")    

                except Exception as e:
                    print(f"Failed forever; {processed_file}; {i}; {e}")

            count += 1
            write_json(data = tracker, filepath = tracker_path)

    print(f"done {done_count}/{count}")


def reprocess_failed_txts(tracker_path):

    def _multi_raw_call(files_data):
        with ThreadPoolExecutor(max_workers=16) as executor:
            indexer_with_sp = partial(indexer.raw_call, system = system_prompt)
            responses = list(executor.map(indexer_with_sp, files_data))
        
        return responses


    system_prompt = """You will be given a corrupt JSON that is not complete. Your job would be to restructure it in the correct format. If there is some sort of delimiter or an ordered list - convert that into a list where each element is of type string. The "arguments" key is a dict containing 2 sub keys called "plaintiff" and "respondent" - which are both lists where each element is of type str"""
    tracker = read_json(tracker_path)

    # when running this function; it is expected to only contain txt files which have been a defect from generation.
    processed_not_converted = tracker["processed_not_converted"]

    num_concurrent = 5

    for i in range(0, len(processed_not_converted), num_concurrent):

        files = processed_not_converted[i: i + num_concurrent]
        files = [file["save_path"] for file in files]

        print(f"{files}; set {i}")

        files_data = [parse_file(file) for file in files]
        responses = _multi_raw_call(files_data)
        for i, response in enumerate(responses):
            if response:
                response = "{" + response
            else:
                print(f"Failed processing from API provider; Sleeping for 5 seconds")
                # sleep(5)
                continue

            save_path = files[i].replace(".txt", ".json")
            try:
                response = json.loads(response)
                _pop_from_tracker(tracker, val = files[i])
                write_json(response, filepath = save_path)
                
                print(f"saved at {save_path}; {i}")
            except Exception as e:
                print(f"Failed converting {files[i]}; {i}; because: {e}")

                try:
                    fixed_string = repair_json(response)
                    # If the string was super broken this will return an empty string - meaning a literaly double quotes as a string-> as per official documentation https://github.com/mangiucugna/json_repair?tab=readme-ov-file
                    # print(fixed_string, len(fixed_string), repr(fixed_string), type(fixed_string))

                    if fixed_string and fixed_string != '""':
                        _json = json.loads(fixed_string)
                        write_json(data = _json, filepath = save_path)
                        
                        _pop_from_tracker(tracker, val = files[i])
                        print(f"saved busted json at {save_path}; {i}")

                    else:
                        print(f"Failed to repair json; {files[i]}; {i}; {e}")    

                except Exception as e:
                    print(f"Failed forever; {files[i]}; {i}; {e}")


        write_json(tracker, tracker_path)
        print("-----------------------")
        print()



def sanitize_json_schema(path = "/mnt/d/work/projects/agents/scripts/processed_data"):
    schema = {
        "judgement": "",
        "case_type": "",
        "case_brief": "",
        "prayers": [],
        "cause_of_action": "",
        "allegation": "",
        "provisions": [],
        "interpretations": [],
        "trial_proceedings": [],
        "misc_details": [],
        "prior_history": [],
        "case_timeline": "",
        "arguments": {"plaintiff": [], "respondent": []},
        "ratio": "",
        "obiter": ""
    }

    # schema as per "case_extraction_prompt_v2"


    indexed_files = [os.path.join(path, file) for file in os.listdir(path)]
    save_dir = "./sanitized"
    os.makedirs(save_dir, exist_ok = True)

    flagged = []
    offset = -1

    for i, indexed_file in enumerate(indexed_files):
        if i < offset:
            continue

        json_data = read_json(indexed_file)
        print(indexed_file)
        for schema_key in schema.keys():
            if schema_key in json_data:
                if isinstance(json_data[schema_key], type(schema[schema_key])):
                    pass
                else:
                    # convert existing json_data[schema_key] to our schema's format
                    print(f"manipulating things at: {indexed_file}; {schema_key} {i}")
                    try:
                        if isinstance(json_data[schema_key], list):
                            json_data[schema_key] = ".\n".join(json_data[schema_key])
                        
                        elif isinstance(json_data[schema_key], str):
                            # you wont be able to always accurately split them since we wont know what to look for. it could sometimes be a ".", "-" or "1. 2. 3." (ordered list)
                            _elements = json_data[schema_key].split(".")
                            json_data[schema_key] = [_ele for _ele in _elements if _ele]

                        elif isinstance(json_data[schema_key], type(None)):
                            json_data[schema_key] = schema[schema_key]

                        else:
                            # case where something is just not the datatype you want it to be in other than str and list
                            print(f"something not right at {indexed_file}; {schema_key}; {i}")
                            flagged.append(indexed_file)
                    except:
                        print(f"something not right at (except) {indexed_file}; {schema_key}; {i}")
                        flagged.append(indexed_file)
                        break

            else:
                try:
                    json_data[schema_key] = schema[schema_key]
                except Exception as e:
                    flagged.append(indexed_file)
                    print(f"Failed to overwrite schema_key {schema_key} for file {indexed_file}")

        save_path = os.path.join(save_dir, indexed_file.split("/")[-1])
        print(save_path)
        write_json(json_data, save_path)
        print()

    flagged = list(set(flagged)) # get only unique files
    print(flagged, len(flagged))
    write_json(flagged, filepath = "./flagged_indexed_files2.json")


        # 1. read json and then convert forcibly convert it into the schema of our kind.
        # 2. If there is a missing key in the indexed_file; then add the key with an empty value of its kind
        # 3. if it is supposed to be a string but is of list; use join to make it a string
        # 4. if it is supposed to be a list but is a string; split at "."


def overwrite_jsons(wrong_jsons_path, tracker_path):
    # replaces them in their own path
    # adds them to the "processed_not_converted" list first
    system_prompt = system_prompt = """You will be given a corrupt JSON that is not complete nor adhering to a particular format. Your job would be to restructure it in the correct format. The following is the schema. Make sure it STRICTLY adheres to this ONLY:
    {
        judgement: // type: str
        case_type: // type: str
        case_brief: // type: str
        prayers: // type: list, each element of type str
        cause_of_action: // type: str
        allegation: // type: str
        provisions: // type: list, each element of type str and each element in the list should contain one provision 
        interpretations: // type: list, each element of type str 
        trial_proceedings: //type: list, each element of type str
        misc_details: // type: list, each element of type str
        prior_history: // type list, each element of type str
        case_timeline: // type: str
        arguments: // type: dict with two keys, "plaintiff" and "respondent"; each key in the dictionary is a list containing the arguments which is of type str
        ratio: // type: str
        obiter: // type: str
    }
    """
    
    def _multi_raw_call(files_data):
        with ThreadPoolExecutor(max_workers=16) as executor:
            indexer_with_sp = partial(indexer.raw_call, system = system_prompt)
            responses = list(executor.map(indexer_with_sp, files_data))
        return responses

    tracker = read_json(tracker_path)
    json_paths = read_json(wrong_jsons_path) # should be a JSON with list of the path to json's that need to be fixed

    json_paths = list(set(json_paths))
    print(f"trying to fix {len(json_paths)}")
    # print(json_paths, type(json_paths))

    num_concurrent = 5

    for i in range(0, len(json_paths), num_concurrent):
        files = json_paths[i: i + num_concurrent]
        print(files)
        files_data = [parse_file(file) for file in files]

        responses = _multi_raw_call(files_data)

        for j, response in enumerate(responses):
            if response:
                response = "{" + response
            else:
                print(f"Failed processing from API provider; Sleeping for 5 seconds; {files[j]}")
                # sleep(5)
                continue

            save_path = files[j] # .replace(".txt", ".json")
            try:
                response = json.loads(response)
                write_json(response, save_path)
                json_paths.remove(files[j])
                print(f"saved at {save_path}; {j}")
            except Exception as e:
                print(f"Failed converting {files[j]}; {j}; because: {e}")

                try:
                    fixed_string = repair_json(response)
                    # If the string was super broken this will return an empty string - meaning a literaly double quotes as a string-> as per official documentation https://github.com/mangiucugna/json_repair?tab=readme-ov-file
                    # print(fixed_string, len(fixed_string), repr(fixed_string), type(fixed_string))

                    if fixed_string and fixed_string != '""':
                        _json = json.loads(fixed_string)
                        write_json(data = _json, filepath = save_path)                        
                        print(f"saved busted json at {save_path}; {j}")
                        json_paths.remove(files[j])

                    else:
                        print(f"Failed to repair json; {files[j]}; {j}; {e}")    

                except Exception as e:
                    print(f"Failed forever; {files[j]}; {j}; {e}")

        write_json(json_paths, wrong_jsons_path)
        print("-----------------------")
        print()



def generate_mapped_json(metadata_json_path, indexed_files_path):
    # metadata_json_path - the path to the json
    # indexed_files_path - the path which contains all the indexed jsons
    metadata_json = read_json(metadata_json_path)
    # indexed_files = [os.path.join(indexed_files_path, file) for file in os.listdir(indexed_files_path)]
    indexed_files = os.listdir(indexed_files_path)

    count = 0

    for i, case_data in enumerate(metadata_json):
        case_data["case_id"] = str(uuid.uuid4())
        # case_data["indexed_file"] = 
        case_save_path = case_data["save_path"].split("/")[-1].replace(".pdf", ".json")
        if case_save_path in indexed_files:
            case_data["indexed_file_path"] = os.path.join(indexed_files_path, case_save_path)
        else:
            print(f"{case_save_path}; {i} not found")
            count += 1
        
    print(f"{count}/{len(metadata_json)} not found")
    write_json(data = metadata_json, filepath = "./final_mapping.json")




if __name__ == "__main__":
    # index_judegments()
    # review_failed()
    # convert_txt_to_jsons(tracker_path = "./tracker_set_full_reindex_900.json")
    # reprocess_failed_txts(tracker_path = "./tracker_set_full_reindex_900.json")
    # sanitize_json_schema() # there seems to be an issue wrt how keys are being checked. sometimes the keys are lists of lists which can pass through sanitization
    # overwrite_jsons(wrong_jsons_path = "./flagged_indexed_files.json", tracker_path = "./tracker_set_full_reindex_900.json")
    
    # generate_mapped_json("/mnt/d/work/datasets/judgements2/final_final_sanitized_cp.json", "/mnt/d/work/projects/agents/scripts/processed_data")
    pass
    # when running this file, please make sure to review and save data as frequent as possible


    




