import textract

def get_brackets(data_string):
    found_opening, found_closing = False, False
    opening_idx, closing_idx = 0, -1

    for i, char in enumerate(data_string):
        if not found_opening:
            if char == "{":
                found_opening = True
                opening_idx = i
            
        if char == "}" and found_opening:
            closing_idx = i

    json_string = data_string[opening_idx : closing_idx + 1]
    return json_string



def parse_file(file_path):
    text = textract.process(file_path).decode("utf-8") 
    # print(text)
    return text
