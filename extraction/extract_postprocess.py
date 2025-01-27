import json
import os
from . import config
# from . import config
def extract_postprocess(input_directory, output_directory ):
    os.makedirs(output_directory, exist_ok=True)
    for filename in os.listdir(input_directory):
            input_file_path = os.path.join(input_directory, filename)
            output_file_path = os.path.join(output_directory, f"{filename}")
            # Load the JSON file
            with open(input_file_path, 'r') as file:
                data = json.load(file)
                filtered_data = [
                    entry for entry in data
                    if len(entry.get('text', '')) >= 20 and all(
                        'Reactant' in reaction for reaction in entry.get('reactions', [])
                    )
                ]
            filtered_data = remove_identical_product_reactant(filtered_data)
            processed_data = array_format(filtered_data)

            with open(output_file_path, 'w') as file:
                json.dump(processed_data, file, indent=4)

            print(f"Filtered data saved to {output_file_path}")
def array_format(results):
    # Postprocess results to ensure correct format for all keys except "text"
    for result in results:
        for key, value in result.items():
            if key == "text":
                continue
            if isinstance(value, list):
                for reaction in value:
                    if isinstance(reaction, dict):
                        for k, v in reaction.items():
                            if isinstance(v, str):
                                # Convert strings to list with proper splitting
                                reaction[k] = [item.strip() for item in v.split(", ")]
            elif isinstance(value, str):
                # Convert any top-level strings to lists if necessary
                result[key] = [item.strip() for item in value.split(", ")]
    return results

def remove_identical_product_reactant(data):
    # Remove entries where "Product" and "Reactant" are the same
    filtered_data = []
    for entry in data:
        reactions = entry.get('reactions', [])
        filtered_reactions = [
            reaction for reaction in reactions
            if reaction.get('Product') != reaction.get('Reactant')
        ]
        if filtered_reactions:
            entry['reactions'] = filtered_reactions
            filtered_data.append(entry)
    return filtered_data
