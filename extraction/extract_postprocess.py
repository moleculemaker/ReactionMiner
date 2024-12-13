import json
import os
from . import config
input_directory  = config.extractFilter_input_directory
output_directory = config.extractFilter_output_directory
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


        with open(output_file_path, 'w') as file:
            json.dump(filtered_data, file, indent=4)

        print(f"Filtered data saved to {output_file_path}")
