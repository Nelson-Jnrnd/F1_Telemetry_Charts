import os

# Get all files in the current directory
files = os.listdir('./vid_img/abudhabi_follow_resampled/')

# Filter for .jpg files
jpg_files = [f for f in files if f.endswith('.jpg')]

# Sort the files to ensure order
jpg_files.sort()

# Path for the output file
output_file_path = '/vid_img/abudhabi_follow_resampled/file_list.txt'

# Write the file paths to the output file
with open(output_file_path, 'w') as output_file:
    for jpg_file in jpg_files:
        output_file.write(f"file '{jpg_file}'\n")

output_file_path