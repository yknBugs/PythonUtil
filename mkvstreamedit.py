import os
import json
import subprocess
import re

def is_prefix_matching(str_a: str, str_b: str):
    """
    Check if str_a is a prefix of str_b or vice versa.
    Return:
    - Whether str_a is a prefix of str_b or vice versa
    - The one has the longer length, if failed, return empty string
    - The difference between the two strings, if failed, return the common maximum prefix
    """
    if len(str_a) > len(str_b):
        if str_a.startswith(str_b):
            return True, str_a, str_a[len(str_b):]
    else:
        if str_b.startswith(str_a):
            return True, str_b, str_b[len(str_a):]
    max_prefix = ""
    for i in range(min(len(str_a), len(str_b))):
        if str_a[i] == str_b[i]:
            max_prefix += str_a[i]
        else:
            break
    return False, "", max_prefix

def get_absolute_file_name(file_name: str):
    """
    Get the file name without extension
    """
    result = file_name.split('.')
    if len(result) <= 1: # No extension
        return file_name
    if len(result) == 2 and result[0] == '':  # .gitignore
        return file_name
    if result[-1] == '': # file end with .
        return file_name
    result = result[:-1]
    return '.'.join(result)

def parse_cmd_args(cmd_args: list) -> str:
    """
    Parse the command line arguments into a string
    """
    result = ''
    if len(cmd_args) == 0:
        return result
    for arg in cmd_args:
        if ' ' in arg:
            if '"' not in arg and "'" not in arg and not arg.startswith('-'):
                result += f'"{arg}" '
            else:
                result += f'{arg} '
        else:
            result += f'{arg} '
    return result[:-1]

def get_video_stream(video_file_path: str, console_feedback: bool = True):
    """
    Get video stream information from a video file, audio file, or even a subtitle file.
    return value is a dictionary with the following structure:
    {
        is_success: bool, (True if the process is successful, False otherwise)
        warning_count: int, (The number of warnings occurred during the process)
        warning_list: [str], (A list of warning messages, can be empty)
        output_log: [str], (The output log of the process, excluding FFmpeg log)
        ffmpeg_log: str, (The FFmpeg log of the process)
        ffmpeg_exit_code: int, (The exit code of FFmpeg process)
        cmd_args: [str], (The command line arguments used to execute FFmpeg)
        exception: [Exception], (The exception occurred during the process, can be empty)
        stream_info: [
            {
                index: int, (0, 1, 2, etc.)
                type: str, (Video, Audio, Subtitle, etc.)
                codec: str, (h264, flac, ass, etc.)
                language: str, (und, eng, chi, jpn, etc.)
            }
        ]
    }
    """
    result = {
        'is_success': False,
        'warning_count': 0,
        'warning_list': [],
        'output_log': [],
        'ffmpeg_log': "",
        'ffmpeg_exit_code': -1,
        'cmd_args': [],
        'exception': [],
        'stream_info': []
    }

    # Check the file
    abs_file_path = os.path.abspath(video_file_path)
    if os.path.exists(abs_file_path) == False:
        result['output_log'].append(f"Error: File {abs_file_path} not found")
        if console_feedback:
            print(f"Error: File {abs_file_path} not found")
        return result
    if os.path.isfile(abs_file_path) == False:
        result['output_log'].append(f"Error: {abs_file_path} is not a file")
        if console_feedback:
            print(f"Error: {abs_file_path} is not a file")
        return result

    # Preparing the command line arguments
    result['cmd_args'] = ['ffmpeg', '-i', abs_file_path]
    result['output_log'].append(f"Info: Reading the metadata of {os.path.basename(abs_file_path)}")
    result['output_log'].append(f"Info: Executing: {parse_cmd_args(result['cmd_args'])}")
    if console_feedback:
        print(f"Reading the metadata of {os.path.basename(abs_file_path)}")

    # Execute FFmpeg
    try:
        process = subprocess.run(result['cmd_args'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        result['ffmpeg_log'] += process.stdout + "\n"
        result['ffmpeg_log'] += process.stderr + "\n"
        result['ffmpeg_exit_code'] = process.returncode
        if process.returncode == 0 or process.returncode == 1:
            result['output_log'].append(f"Info: FFmpeg process exited with code: {process.returncode}")
            if console_feedback:
                print(f"FFmpeg process exited with code: {process.returncode}")
        else:
            result['warning_count'] += 1
            result['warning_list'].append(f"FFmpeg process terminated with code {process.returncode}")
            result['output_log'].append(f"Warning: FFmpeg process terminated with code {process.returncode}")
            if console_feedback:
                print(f"Warning: FFmpeg process terminated with code {process.returncode}")
    except Exception as e:
        result['warning_count'] += 1
        result['warning_list'].append(f"Caught Exception when trying to read metadata of {os.path.basename(abs_file_path)}: {str(e)}")
        result['output_log'].append(f"Warning: Caught Exception when trying to read metadata of {os.path.basename(abs_file_path)}: {str(e)}")
        result['exception'].append(e)
        if console_feedback:
            print(f"Warning: Caught Exception when trying to read metadata of {os.path.basename(abs_file_path)}: {str(e)}")

    # Parse the output log
    try:
        stream_info = re.findall(r'Stream #(\d+):(\d+)(.*): (\w+): (\w+)', result['ffmpeg_log'])
        info_index = 0
        for file_index, stream_index, lang, stream_type, codec in stream_info:
            try:
                info_index += 1
                # Validations
                if file_index != '0':
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Found unexpected stream index #{file_index}:{stream_index}")
                    result['output_log'].append(f"Warning: Found unexpected stream index #{file_index}:{stream_index}")
                    if console_feedback:
                        print(f"Warning: Found unexpected stream index #{file_index}:{stream_index}")
                language = lang
                if language == '':
                    language = '(und)'
                if language.endswith(')'):
                    bracket_index = language.find('(')
                    if bracket_index >= 0:
                        language = language[bracket_index:]
                if language.startswith('(') and language.endswith(')'):
                    language = language[1:-1]
                else:
                    language = lang
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Found unexpected language code {lang}")
                    result['output_log'].append(f"Warning: Found unexpected language code {lang}")
                    if console_feedback:
                        print(f"Warning: Found unexpected language code {lang}")
                if stream_type not in ['Video', 'Audio', 'Subtitle']:
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Found unexpected stream type {stream_type}")
                    result['output_log'].append(f"Warning: Found unexpected stream type {stream_type}")
                    if console_feedback:
                        print(f"Warning: Found unexpected stream type {stream_type}")

                # Writing the stream info
                result['stream_info'].append({
                    'index': int(stream_index),
                    'type': stream_type,
                    'codec': codec,
                    'language': language
                })
                result['output_log'].append(f"Info: Stream #{stream_index}: {stream_type} - {codec} - {language}")
                if console_feedback:
                    print(f"Stream #{stream_index}: {stream_type} - {codec} - {language}")
            except Exception as ex:
                result['warning_count'] += 1
                result['warning_list'].append(f"Caught Exception when trying to parse the stream {info_index} info: {str(ex)}")
                result['output_log'].append(f"Warning: Caught Exception when trying to parse the stream {info_index} info: {str(ex)}")
                result['output_log'].append(f"Debug: file_index = {file_index}, stream_index = {stream_index}, lang = {lang}, stream_type = {stream_type}, codec = {codec}")
                result['exception'].append(ex)
                if console_feedback:
                    print(f"Warning: Caught Exception when trying to parse the stream {info_index} info: {str(ex)}")
    except Exception as e:
        result['warning_count'] += 1
        result['warning_list'].append(f"Caught Exception when trying to parse metadata of {os.path.basename(abs_file_path)}: {str(e)}")
        result['output_log'].append(f"Warning: Caught Exception when trying to parse metadata of {os.path.basename(abs_file_path)}: {str(e)}")
        result['exception'].append(e)
        if console_feedback:
            print(f"Warning: Caught Exception when trying to parse metadata of {os.path.basename(abs_file_path)}: {str(e)}")
    if len(stream_info) == 0:
        result['warning_count'] += 1
        result['warning_list'].append(f"No stream found for {os.path.basename(abs_file_path)}")
        result['output_log'].append(f"Warning: No stream found for {os.path.basename(abs_file_path)}")
        if console_feedback:
            print(f"Warning: No stream found for {os.path.basename(abs_file_path)}")

    result['is_success'] = True
    return result

def merge_video_stream(video_folder_path, 
                       output_folder_path, 
                       encoding_sub = True,
                       disable_ffmpeg_merge = False, 
                       write_ffmpeg_log = False,
                       save_log_file = True,
                       save_json_file = False,
                       console_feedback = True):
    """
    Merge video streams with similar file names in a folder
    Input:
    - video_folder_path: str, the path of the folder containing video files
    - output_folder_path: str, the path of the folder to save the output files
    - encoding_sub: bool, True if encoding subtitles, False will directly copy the subtitle streams
    - disable_ffmpeg_merge: bool, True to only generate the merging command but not execute it, will also force disable output.log and output.json
    - write_ffmpeg_log: bool, True to write the FFmpeg log to the output log, False otherwise
    - save_log_file: bool, True to save the output log to a output.log file, False otherwise
    - save_json_file: bool, True to save the output log to a output.json file, False otherwise
    - console_feedback: bool, True to print the output log to the console, False otherwise
    Return value is a dictionary with the following structure:
    {
        task_count: int, (The number of tasks to be executed)
        success_count: int, (The number of tasks executed successfully)
        failed_count: int, (The number of tasks failed)
        warning_count: int, (The number of warnings occurred during the process)
        warning_list: [str], (A list of warning messages, can be empty)
        output_log: [str], (The output log of the process, excluding FFmpeg log)
        exception: [Exception], (The exception occurred during the process, can be empty)
        task: [
            {
                task_id: int, (The task ID)
                is_success: bool, (True if the process is successful, False otherwise)
                ffmpeg_log: str, (The FFmpeg log of the process when merging the streams)
                ffmpeg_exit_code: int, (The exit code of FFmpeg process when merging the streams)
                cmd_args: (The command line arguments used to execute FFmpeg when merging the streams)
                input_files: [
                    {
                        index: int, (0, 1, 2, etc.)
                        file_path: str, (The file path of the input file)
                        ffmpeg_log: str, (The FFmpeg log of the process when reading the metadata of the input file)
                        ffmpeg_exit_code: int, (The exit code of FFmpeg process when reading the metadata of the input file)
                        is_success: bool, (if reading the metadata of the input file is successful)
                        cmd_args: [str], (The command line arguments used to execute FFmpeg when reading the metadata of the input file)
                        stream_info: [
                            {
                                index: int, (0, 1, 2, etc.)
                                type: str, (Video, Audio, Subtitle, etc.)
                                codec: str, (h264, flac, etc.)
                                language: str, (und, eng, chi, jpn, etc.)
                                output_index: int, (The index of the output file)
                            }
                        ]
                    }
                ]
            }
        ]
    }
    """
    result = {
        'task_count': 0,
        'success_count': 0,
        'failed_count': 0,
        'warning_count': 0,
        'warning_list': [],
        'output_log': [],
        'exception': [],
        'task': []
    }
    has_fatal_error = False

    # Check the folder
    if os.path.exists(video_folder_path) == False:
        result['warning_count'] += 1
        result['warning_list'].append(f"Input folder {video_folder_path} not found")
        result['output_log'].append(f"Warning: Input folder {video_folder_path} not found")
        if console_feedback:
            print(f"Warning: Input folder {video_folder_path} not found")
        has_fatal_error = True
    if has_fatal_error == False and os.path.isdir(video_folder_path) == False:
        result['warning_count'] += 1
        result['warning_list'].append(f"Input path {video_folder_path} is not a folder")
        result['output_log'].append(f"Warning: Input path {video_folder_path} is not a folder")
        if console_feedback:
            print(f"Warning: Input path {video_folder_path} is not a folder")
        has_fatal_error = True

    # Check the output folder, if not exist, create it, no need to check this if disable_ffmpeg_merge is True
    if disable_ffmpeg_merge == False:
        if has_fatal_error == False and os.path.exists(output_folder_path) == False:
            try:
                os.makedirs(output_folder_path)
                result['warning_count'] += 1
                result['warning_list'].append(f"Output folder {output_folder_path} not found, created it")
                result['output_log'].append(f"Warning: Output folder {output_folder_path} not found, created it")
                if console_feedback:
                    print(f"Warning: Output folder {output_folder_path} not found, created it")
            except Exception as e:
                result['warning_count'] += 1
                result['warning_list'].append(f"Failed to create output folder {output_folder_path}: {str(e)}")
                result['output_log'].append(f"Warning: Failed to create output folder {output_folder_path}: {str(e)}")
                result['exception'].append(e)
                if console_feedback:
                    print(f"Warning: Failed to create output folder {output_folder_path}: {str(e)}")
                has_fatal_error = True
        if has_fatal_error == False and os.path.isdir(output_folder_path) == False:
            result['warning_count'] += 1
            result['warning_list'].append(f"Output path {output_folder_path} is not a folder")
            result['output_log'].append(f"Warning: Output path {output_folder_path} is not a folder")
            if console_feedback:
                print(f"Warning: Output path {output_folder_path} is not a folder")
            has_fatal_error = True
        if has_fatal_error == False and len(os.listdir(output_folder_path)) > 0:
            result['warning_count'] += 1
            result['warning_list'].append(f"Output folder {output_folder_path} is not empty")
            result['output_log'].append(f"Warning: Output folder {output_folder_path} is not empty")
            if console_feedback:
                print(f"Warning: Output folder {output_folder_path} is not empty")

    # Get the list of video files
    folder_files = []
    video_files = []
    audio_files = []
    subtitle_files = []
    files_use_counter = []
    if has_fatal_error == False:
        folder_files = os.listdir(video_folder_path)
        for file in folder_files:
            if os.path.isdir(os.path.join(video_folder_path, file)) or file.startswith('.') or file.startswith('Thumbs.db') or file.startswith('desktop.ini'):
                result['output_log'].append(f"Info: Exclude {os.path.join(video_folder_path, file)} in the input folder")
                if console_feedback:
                    print(f"Exclude {file} in the input folder")
        folder_files = [file for file in folder_files if not os.path.isdir(os.path.join(video_folder_path, file)) and not file.startswith('.') and not file.startswith('Thumbs.db') and not file.startswith('desktop.ini')]
        
        video_files = [os.path.join(video_folder_path, video_file) for video_file in folder_files if video_file.endswith('.mp4') or video_file.endswith('.mkv') or video_file.endswith('.rmvb') or video_file.endswith('.flv')]
        audio_files = [os.path.join(video_folder_path, audio_file) for audio_file in folder_files if audio_file.endswith('.mp3') or audio_file.endswith('.flac') or audio_file.endswith('.wav') or audio_file.endswith('.mka')]
        subtitle_files = [os.path.join(video_folder_path, subtitle_file) for subtitle_file in folder_files if subtitle_file.endswith('.srt') or subtitle_file.endswith('.ass') or subtitle_file.endswith('.sup')]
        files_use_counter = [0] * len(folder_files) # Check if the file is never used or used multiple times

    # Executing each task
    task_id = 0
    for video_file in video_files:
        if has_fatal_error:
            break

        task_id += 1
        task = {
            'task_id': task_id,
            'is_success': False,
            'ffmpeg_log': "",
            'ffmpeg_exit_code': -1,
            'cmd_args': ['ffmpeg'],
            'input_files': []
        }
        result['output_log'].append(f"Info: Processing task {task_id}/{len(video_files)}")
        if console_feedback:
            print(f"Processing task {task_id}/{len(video_files)}")

        cmd_input_args = []
        cmd_map_args = []
        cmd_metadata_args = []
        cmd_disposition_args = []

        video_stream_file_index = []
        video_stream_stream_index = []
        audio_stream_file_index = []
        audio_stream_stream_index = []
        subtitle_stream_file_index = []
        subtitle_stream_stream_index = []
        other_stream_file_index = []
        other_stream_stream_index = []

        input_file_index = 0
        input_stream_index = 0
        # Process input video file
        input_file = {
            'index': input_file_index,
            'file_path': video_file,
            'ffmpeg_log': "",
            'ffmpeg_exit_code': -1,
            'is_success': False,
            'cmd_args': ['ffmpeg', '-i', video_file],
            'stream_info': []
        }
        for i, file in enumerate(folder_files):
            if file == os.path.basename(video_file):
                files_use_counter[i] += 1
        result['output_log'].append(f"Info: Input file #{input_file_index}: {video_file}")
        if console_feedback:
            print(f"Input file #{input_file_index}: {os.path.basename(video_file)}")

        input_file_metadata = get_video_stream(video_file, console_feedback=console_feedback)
        result['warning_count'] += input_file_metadata['warning_count']
        result['warning_list'].extend(input_file_metadata['warning_list'])
        result['output_log'].extend(input_file_metadata['output_log'])
        result['exception'].extend(input_file_metadata['exception'])
        input_file['ffmpeg_log'] = input_file_metadata['ffmpeg_log']
        input_file['ffmpeg_exit_code'] = input_file_metadata['ffmpeg_exit_code']
        input_file['is_success'] = input_file_metadata['is_success']
        input_file['cmd_args'] = input_file_metadata['cmd_args']
        for info in input_file_metadata['stream_info']:
            input_file_stream_info = {
                'index': info['index'],
                'type': info['type'],
                'codec': info['codec'],
                'language': info['language'],
                'output_index': -1 # Not assigned yet
            }
            input_file['stream_info'].append(input_file_stream_info)
            if info['type'] == 'Video':
                video_stream_file_index.append(input_file_index)
                video_stream_stream_index.append(info['index'])
            elif info['type'] == 'Audio':
                audio_stream_file_index.append(input_file_index)
                audio_stream_stream_index.append(info['index'])
            elif info['type'] == 'Subtitle':
                subtitle_stream_file_index.append(input_file_index)
                subtitle_stream_stream_index.append(info['index'])
            else:
                other_stream_file_index.append(input_file_index)
                other_stream_stream_index.append(info['index'])
        task['input_files'].append(input_file)
        cmd_input_args.extend(['-i', video_file])
        input_file_index += 1

        # Process input audio files
        for audio_file in audio_files:
            is_file_name_match, full_file_name, diff_file_name = is_prefix_matching(get_absolute_file_name(os.path.basename(video_file)), get_absolute_file_name(os.path.basename(audio_file)))
            if is_file_name_match:
                input_file = {
                    'index': input_file_index,
                    'file_path': audio_file,
                    'ffmpeg_log': "",
                    'ffmpeg_exit_code': -1,
                    'is_success': False,
                    'cmd_args': ['ffmpeg', '-i', audio_file],
                    'stream_info': []
                }
                for i, file in enumerate(folder_files):
                    if file == os.path.basename(audio_file):
                        files_use_counter[i] += 1
                result['output_log'].append(f"Info: Input file #{input_file_index}: {audio_file}")
                if console_feedback:
                    print(f"Input file #{input_file_index}: {os.path.basename(audio_file)}")

                input_file_metadata = get_video_stream(audio_file, console_feedback=console_feedback)
                result['warning_count'] += input_file_metadata['warning_count']
                result['warning_list'].extend(input_file_metadata['warning_list'])
                result['output_log'].extend(input_file_metadata['output_log'])
                result['exception'].extend(input_file_metadata['exception'])
                input_file['ffmpeg_log'] = input_file_metadata['ffmpeg_log']
                input_file['ffmpeg_exit_code'] = input_file_metadata['ffmpeg_exit_code']
                input_file['is_success'] = input_file_metadata['is_success']
                input_file['cmd_args'] = input_file_metadata['cmd_args']
                for info in input_file_metadata['stream_info']:
                    input_file_stream_info = {
                        'index': info['index'],
                        'type': info['type'],
                        'codec': info['codec'],
                        'language': info['language'],
                        'output_index': -1 # Not assigned yet
                    }
                    input_file['stream_info'].append(input_file_stream_info)
                    if info['type'] == 'Video':
                        video_stream_file_index.append(input_file_index)
                        video_stream_stream_index.append(info['index'])
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Found unexpected video stream #{info['index']} in audio file: {audio_file}")
                        result['output_log'].append(f"Warning: Found unexpected video stream #{info['index']} in audio file: {audio_file}")
                        if console_feedback:
                            print(f"Warning: Found unexpected video stream #{info['index']} in audio file: {os.path.basename(audio_file)}")
                    elif info['type'] == 'Audio':
                        audio_stream_file_index.append(input_file_index)
                        audio_stream_stream_index.append(info['index'])
                    elif info['type'] == 'Subtitle':
                        subtitle_stream_file_index.append(input_file_index)
                        subtitle_stream_stream_index.append(info['index'])
                    else:
                        other_stream_file_index.append(input_file_index)
                        other_stream_stream_index.append(info['index'])
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Found unexpected stream #{info['index']} in audio file: {audio_file}")
                        result['output_log'].append(f"Warning: Found unexpected stream #{info['index']} in audio file: {audio_file}")
                        if console_feedback:
                            print(f"Warning: Found unexpected stream #{info['index']} in audio file: {os.path.basename(audio_file)}")
                task['input_files'].append(input_file)
                cmd_input_args.extend(['-i', audio_file])
                input_file_index += 1

        # Process input subtitle files
        for subtitle_file in subtitle_files:
            is_file_name_match, full_file_name, diff_file_name = is_prefix_matching(get_absolute_file_name(os.path.basename(video_file)), get_absolute_file_name(os.path.basename(subtitle_file)))
            if is_file_name_match:
                input_file = {
                    'index': input_file_index,
                    'file_path': subtitle_file,
                    'ffmpeg_log': "",
                    'ffmpeg_exit_code': -1,
                    'is_success': False,
                    'cmd_args': ['ffmpeg', '-i', subtitle_file],
                    'stream_info': []
                }
                for i, file in enumerate(folder_files):
                    if file == os.path.basename(subtitle_file):
                        files_use_counter[i] += 1
                result['output_log'].append(f"Info: Input file #{input_file_index}: {subtitle_file}")
                if console_feedback:
                    print(f"Input file #{input_file_index}: {os.path.basename(subtitle_file)}")

                input_file_metadata = get_video_stream(subtitle_file, console_feedback=console_feedback)
                result['warning_count'] += input_file_metadata['warning_count']
                result['warning_list'].extend(input_file_metadata['warning_list'])
                result['output_log'].extend(input_file_metadata['output_log'])
                result['exception'].extend(input_file_metadata['exception'])
                input_file['ffmpeg_log'] = input_file_metadata['ffmpeg_log']
                input_file['ffmpeg_exit_code'] = input_file_metadata['ffmpeg_exit_code']
                input_file['is_success'] = input_file_metadata['is_success']
                input_file['cmd_args'] = input_file_metadata['cmd_args']
                subtitle_stream_count = 0
                for info in input_file_metadata['stream_info']:
                    input_file_stream_info = {
                        'index': info['index'],
                        'type': info['type'],
                        'codec': info['codec'],
                        'language': info['language'],
                        'output_index': -1 # Not assigned yet
                    }
                    input_file['stream_info'].append(input_file_stream_info)
                    if info['type'] == 'Video':
                        video_stream_file_index.append(input_file_index)
                        video_stream_stream_index.append(info['index'])
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Found unexpected video stream #{info['index']} in subtitle file: {subtitle_file}")
                        result['output_log'].append(f"Warning: Found unexpected video stream #{info['index']} in subtitle file: {subtitle_file}")
                        if console_feedback:
                            print(f"Warning: Found unexpected video stream #{info['index']} in subtitle file: {os.path.basename(subtitle_file)}")
                    elif info['type'] == 'Audio':
                        audio_stream_file_index.append(input_file_index)
                        audio_stream_stream_index.append(info['index'])
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Found unexpected audio stream #{info['index']} in subtitle file: {subtitle_file}")
                        result['output_log'].append(f"Warning: Found unexpected audio stream #{info['index']} in subtitle file: {subtitle_file}")
                        if console_feedback:
                            print(f"Warning: Found unexpected audio stream #{info['index']} in subtitle file: {os.path.basename(subtitle_file)}")
                    elif info['type'] == 'Subtitle':
                        subtitle_stream_count += 1
                        subtitle_stream_file_index.append(input_file_index)
                        subtitle_stream_stream_index.append(info['index'])
                    else:
                        other_stream_file_index.append(input_file_index)
                        other_stream_stream_index.append(info['index'])
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Found unexpected stream #{info['index']} in subtitle file: {subtitle_file}")
                        result['output_log'].append(f"Warning: Found unexpected stream #{info['index']} in subtitle file: {subtitle_file}")
                        if console_feedback:
                            print(f"Warning: Found unexpected stream #{info['index']} in subtitle file: {os.path.basename(subtitle_file)}")
                if subtitle_stream_count > 1:
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Found {subtitle_stream_count} subtitle streams in subtitle file: {subtitle_file}")
                    result['output_log'].append(f"Warning: Found {subtitle_stream_count} subtitle streams in subtitle file: {subtitle_file}")
                    if console_feedback:
                        print(f"Warning: Found {subtitle_stream_count} subtitle streams in subtitle file: {os.path.basename(subtitle_file)}")
                task['input_files'].append(input_file)
                cmd_input_args.extend(['-i', subtitle_file])
                input_file_index += 1
        
        if len(video_stream_stream_index) > 1:
            result['warning_count'] += 1
            result['warning_list'].append(f"Merge {len(video_stream_stream_index)} video streams into one file.")
            result['output_log'].append(f"Warning: Merge {len(video_stream_stream_index)} video streams into one file.")
            if console_feedback:
                print(f"Warning: Merge {len(video_stream_stream_index)} video streams into one file.")
        if len(video_stream_file_index) == 0:
            result['warning_count'] += 1
            result['warning_list'].append(f"No video stream found in {video_file}")
            result['output_log'].append(f"Warning: No video stream found in {video_file}")
            if console_feedback:
                print(f"Warning: No video stream found in {os.path.basename(video_file)}")
        if input_file_index <= 1:
            result['warning_count'] += 1
            result['warning_list'].append(f"No matching file found for {video_file}")
            result['output_log'].append(f"Warning: No matching file found for {video_file}")
            if console_feedback:
                print(f"Warning: No matching file found for {os.path.basename(video_file)}")

        # Create Stream mapping
        for i in range(len(video_stream_stream_index)):
            cmd_map_args.extend(['-map', f'{video_stream_file_index[i]}:{video_stream_stream_index[i]}'])
            task['input_files'][video_stream_file_index[i]]['stream_info'][video_stream_stream_index[i]]['output_index'] = input_stream_index
            result['output_log'].append(f"Info: Stream #{video_stream_file_index[i]}:{video_stream_stream_index[i]} -> Stream #{input_stream_index} [Video #{i}] (from {task['input_files'][video_stream_file_index[i]]['file_path']})")
            if console_feedback:
                print(f"Stream #{video_stream_file_index[i]}:{video_stream_stream_index[i]} -> Stream #{input_stream_index} [Video #{i}] (from {os.path.basename(task['input_files'][video_stream_file_index[i]]['file_path'])})")
            input_stream_index += 1
        for i in range(len(audio_stream_stream_index)):
            cmd_map_args.extend(['-map', f'{audio_stream_file_index[i]}:{audio_stream_stream_index[i]}'])
            task['input_files'][audio_stream_file_index[i]]['stream_info'][audio_stream_stream_index[i]]['output_index'] = input_stream_index
            result['output_log'].append(f"Info: Stream #{audio_stream_file_index[i]}:{audio_stream_stream_index[i]} -> Stream #{input_stream_index} [Audio #{i}] (from {task['input_files'][audio_stream_file_index[i]]['file_path']})")
            if console_feedback:
                print(f"Stream #{audio_stream_file_index[i]}:{audio_stream_stream_index[i]} -> Stream #{input_stream_index} [Audio #{i}] (from {os.path.basename(task['input_files'][audio_stream_file_index[i]]['file_path'])})")
            input_stream_index += 1
        for i in range(len(subtitle_stream_stream_index)):
            cmd_map_args.extend(['-map', f'{subtitle_stream_file_index[i]}:{subtitle_stream_stream_index[i]}'])
            task['input_files'][subtitle_stream_file_index[i]]['stream_info'][subtitle_stream_stream_index[i]]['output_index'] = input_stream_index
            # Subtitle in subtitle files need metadata, in video or audio files just copy the metadata
            if task['input_files'][subtitle_stream_file_index[i]]['file_path'] in subtitle_files:
                is_file_name_match, full_file_name, diff_file_name = is_prefix_matching(get_absolute_file_name(os.path.basename(video_file)), get_absolute_file_name(os.path.basename(task['input_files'][subtitle_stream_file_index[i]]['file_path'])))
                metadata_title = diff_file_name + '.' + os.path.basename(task['input_files'][subtitle_stream_file_index[i]]['file_path']).split('.')[-1]
                if len(metadata_title) > 1 and metadata_title[0] == '.':
                    metadata_title = metadata_title[1:]
                if len(metadata_title) == 0 or metadata_title == '.':
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Subtitle file {task['input_files'][subtitle_stream_file_index[i]]['file_path']} has no valid title")
                    result['output_log'].append(f"Warning: Subtitle file {task['input_files'][subtitle_stream_file_index[i]]['file_path']} has no valid title")
                    if console_feedback:
                        print(f"Warning: Subtitle file {os.path.basename(task['input_files'][subtitle_stream_file_index[i]]['file_path'])} has no valid title")
                cmd_metadata_args.extend([f'-metadata:s:{input_stream_index}', f'title="{metadata_title}"'])
                result['output_log'].append(f"Info: Stream #{subtitle_stream_file_index[i]}:{subtitle_stream_stream_index[i]} -> Stream #{input_stream_index} [Subtitle #{i}: {metadata_title}] (from {task['input_files'][subtitle_stream_file_index[i]]['file_path']})")
                if console_feedback:
                    print(f"Stream #{subtitle_stream_file_index[i]}:{subtitle_stream_stream_index[i]} -> Stream #{input_stream_index} [Subtitle #{i}: {metadata_title}] (from {os.path.basename(task['input_files'][subtitle_stream_file_index[i]]['file_path'])})")
            else:
                result['output_log'].append(f"Info: Stream #{subtitle_stream_file_index[i]}:{subtitle_stream_stream_index[i]} -> Stream #{input_stream_index} [Subtitle #{i}] (from {task['input_files'][subtitle_stream_file_index[i]]['file_path']})")
                if console_feedback:
                    print(f"Stream #{subtitle_stream_file_index[i]}:{subtitle_stream_stream_index[i]} -> Stream #{input_stream_index} [Subtitle #{i}] (from {os.path.basename(task['input_files'][subtitle_stream_file_index[i]]['file_path'])})")
            input_stream_index += 1
        for i in range(len(other_stream_stream_index)):
            cmd_map_args.extend(['-map', f'{other_stream_file_index[i]}:{other_stream_stream_index[i]}'])
            task['input_files'][other_stream_file_index[i]]['stream_info'][other_stream_stream_index[i]]['output_index'] = input_stream_index
            result['output_log'].append(f"Info: Stream #{other_stream_file_index[i]}:{other_stream_stream_index[i]} -> Stream #{input_stream_index} (from {task['input_files'][other_stream_file_index[i]]['file_path']})")
            if console_feedback:
                print(f"Stream #{other_stream_file_index[i]}:{other_stream_stream_index[i]} -> Stream #{input_stream_index} (from {os.path.basename(task['input_files'][other_stream_file_index[i]]['file_path'])})")
            input_stream_index += 1
        
        # Preparing the command line arguments
        if len(audio_stream_stream_index) > 0:
            cmd_disposition_args.extend(['-disposition:a:0', 'default'])
        if len(subtitle_stream_stream_index) > 0:
            cmd_disposition_args.extend(['-disposition:s:0', 'default'])
        task['cmd_args'].extend(cmd_input_args)
        task['cmd_args'].extend(cmd_map_args)
        task['cmd_args'].extend(cmd_metadata_args)
        task['cmd_args'].extend(cmd_disposition_args)
        if encoding_sub:
            task['cmd_args'].extend(['-c:v', 'copy', '-c:a', 'copy'])
        else:
            task['cmd_args'].extend(['-c', 'copy'])
        output_file = os.path.join(output_folder_path, get_absolute_file_name(os.path.basename(video_file)) + '.mkv')
        task['cmd_args'].append(output_file)

        # Check if the output file exists
        if os.path.exists(output_file) and disable_ffmpeg_merge == False:
            result['warning_count'] += 1
            result['warning_list'].append(f"Output file {output_file} already exists, will be overwritten")
            result['output_log'].append(f"Warning: Output file {output_file} already exists, will be overwritten")
            if console_feedback:
                print(f"Warning: Output file {os.path.basename(output_file)} already exists, will be overwritten")
            os.remove(output_file)
        
        # Execute FFmpeg
        if disable_ffmpeg_merge == True:
            result['output_log'].append(f"Info: Merge {input_file_index} files into {output_file}")
            result['output_log'].append(f"Info: Command: {parse_cmd_args(task['cmd_args'])}")
            task['ffmpeg_log'] += "FFmpeg process is disabled"
            task['ffmpeg_exit_code'] = 0
            task['is_success'] = True
            result['task_count'] += 1
            result['success_count'] += 1
            result['task'].append(task)
            if console_feedback:
                print(f"Merge {input_file_index} files into {os.path.basename(output_file)}")
                print(f"Command: {parse_cmd_args(task['cmd_args'])}")
        else:
            result['output_log'].append(f"Info: Merging {input_file_index} files into {output_file}")
            result['output_log'].append(f"Info: Executing: {parse_cmd_args(task['cmd_args'])}")
            if console_feedback:
                print(f"Merging {input_file_index} files into {os.path.basename(output_file)}")
            try:
                process = subprocess.run(task['cmd_args'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                task['ffmpeg_log'] += process.stdout + "\n"
                task['ffmpeg_log'] += process.stderr + "\n"
                if write_ffmpeg_log:
                    result['output_log'].append(task['ffmpeg_log'])
                task['ffmpeg_exit_code'] = process.returncode
                try:
                    possible_ffmpeg_warning = re.findall(r'\[(.+) @ ([0123456789abcdef]{16})\] (.+)', task['ffmpeg_log'])
                    ffmpeg_warning_index = 0
                    for target_muxer, muxer_id, log_content in possible_ffmpeg_warning:
                        if write_ffmpeg_log == False:
                            result['output_log'].append(f"Info: FFmpeg: [{target_muxer} @ {muxer_id}] {log_content}")
                            if console_feedback:
                                print(f"FFmpeg: [{target_muxer} @ {muxer_id}] {log_content}")
                        ffmpeg_warning_index += 1
                    if ffmpeg_warning_index > 1 and process.returncode == 0:
                        # Usually only one result: [out#0/matroska @ 0123456789abcdef] video:1234kb audio:567kb subtitle:89kb other streams:0kb global headers:5kb muxing overhead: 0.0123456%
                        result['warning_count'] += 1
                        result['warning_list'].append(f"FFmpeg may have reported {ffmpeg_warning_index - 1} warnings, check the log for details")
                        result['output_log'].append(f"Warning: FFmpeg may have reported {ffmpeg_warning_index - 1} warnings, check the log for details")
                        if console_feedback:
                            print(f"Warning: FFmpeg may have reported {ffmpeg_warning_index - 1} warnings, check the log for details")
                    if ffmpeg_warning_index < 1 and process.returncode == 0:
                        result['warning_count'] += 1
                        result['warning_list'].append(f"Unable to find FFmpeg output summary.")
                        result['output_log'].append(f"Warning: Unable to find FFmpeg output summary.")
                        if console_feedback:
                            print(f"Warning: Unable to find FFmpeg output summary.")
                except Exception as e:
                    result['warning_count'] += 1
                    result['warning_list'].append(f"Failed to parse FFmpeg output: {str(e)}")
                    result['output_log'].append(f"Warning: Failed to parse FFmpeg output: {str(e)}")
                    result['exception'].append(e)
                    if console_feedback:
                        print(f"Warning: Failed to parse FFmpeg output: {str(e)}")
                if process.returncode == 0:
                    task['is_success'] = True
                    result['task_count'] += 1
                    result['success_count'] += 1
                    result['output_log'].append(f"Info: FFmpeg process exited with code: {process.returncode}")
                    result['output_log'].append(f"Info: Merge {input_file_index} files into {output_file} successfully")
                    result['task'].append(task)
                    if console_feedback:
                        print(f"FFmpeg process exited with code: {process.returncode}")
                        print(f"Merge {input_file_index} files into {os.path.basename(output_file)} successfully")
                else:
                    result['task_count'] += 1
                    result['failed_count'] += 1
                    result['output_log'].append(f"Error: FFmpeg process terminated with code {process.returncode}")
                    result['output_log'].append(f"Error: Merge {input_file_index} files into {output_file} failed")
                    result['task'].append(task)
                    if console_feedback:
                        print(f"Error: FFmpeg process terminated with code {process.returncode}")
                        print(f"Error: Merge {input_file_index} files into {os.path.basename(output_file)} failed")
            except Exception as e:
                result['task_count'] += 1
                result['failed_count'] += 1
                result['output_log'].append(f"Error: Caught Exception when trying to merge {input_file_index} files into {output_file}: {str(e)}")
                result['task'].append(task)
                result['exception'].append(e)
                if console_feedback:
                    print(f"Error: Caught Exception when trying to merge {input_file_index} files into {os.path.basename(output_file)}: {str(e)}")
    # Check if there are files never used or used multiple times
    if has_fatal_error == False:
        for i, file in enumerate(folder_files):
            if files_use_counter[i] == 0:
                result['warning_count'] += 1
                result['warning_list'].append(f"File {file} is never used")
                result['output_log'].append(f"Warning: File {file} is never used")
                if console_feedback:
                    print(f"Warning: File {file} is never used")
            elif files_use_counter[i] > 1:
                result['warning_count'] += 1
                result['warning_list'].append(f"File {file} is used {files_use_counter[i]} times")
                result['output_log'].append(f"Warning: File {file} is used {files_use_counter[i]} times")
                if console_feedback:
                    print(f"Warning: File {file} is used {files_use_counter[i]} times")
    
    # Check if the log file already exists
    log_file = os.path.join(output_folder_path, 'output.log')
    json_file = os.path.join(output_folder_path, 'output.json')
    if disable_ffmpeg_merge == False and has_fatal_error == False:    
        if save_log_file:
            if os.path.exists(log_file):
                result['warning_count'] += 1
                result['warning_list'].append(f"Log file {log_file} already exists, will be overwritten")
                result['output_log'].append(f"Warning: Log file {log_file} already exists, will be overwritten")
                if console_feedback:
                    print(f"Warning: Log file {os.path.basename(log_file)} already exists, will be overwritten")
                os.remove(log_file)
        if save_json_file:
            if os.path.exists(json_file):
                result['warning_count'] += 1
                result['warning_list'].append(f"JSON file {json_file} already exists, will be overwritten")
                result['output_log'].append(f"Warning: JSON file {json_file} already exists, will be overwritten")
                if console_feedback:
                    print(f"Warning: JSON file {os.path.basename(json_file)} already exists, will be overwritten")
                os.remove(json_file)

    if task_id == 0 and has_fatal_error == False:
        result['warning_count'] += 1
        result['warning_list'].append(f"No task is executed")
        result['output_log'].append(f"Warning: No task is executed")
        if console_feedback:
            print(f"Warning: No task is executed")
    result['output_log'].append(f"Info: {result['task_count']} tasks done, {result['success_count']} success, {result['failed_count']} failed, {result['warning_count']} warnings")
    if console_feedback:
        print(f"{result['task_count']} tasks done, {result['success_count']} success, {result['failed_count']} failed, {result['warning_count']} warnings")

    # Save the log file
    if disable_ffmpeg_merge == False and has_fatal_error == False:
        try:
            if save_log_file:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(result['output_log']))
        except Exception as e:
            if console_feedback:
                print(f"Error: Failed to save log file: {str(e)}")

        try:
            if save_json_file:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4)
        except Exception as e:
            if console_feedback:
                print(f"Error: Failed to save JSON file: {str(e)}")

    return result

def batch_rename(map_function, folder_path, console_feedback=True):
    result = {
        'task_count': 0,
        'success_count': 0,
        'failed_count': 0,
        'output_log': [],
        'exception': []
    }

    if os.path.exists(folder_path) == False:
        result['output_log'].append(f"Error: {folder_path} not found")
        if console_feedback:
            print(f"Error: {folder_path} not found")
        return result
    if os.path.isfile(folder_path):
        try:
            new_file_name = map_function(os.path.basename(folder_path))
            new_file_name = os.path.join(os.path.dirname(folder_path), new_file_name)
            os.rename(folder_path, new_file_name)
            result['task_count'] += 1
            result['success_count'] += 1
            result['output_log'].append(f"Info: {os.path.basename(folder_path)} -> {os.path.basename(new_file_name)}")
            if console_feedback:
                print(f"{os.path.basename(folder_path)} -> {os.path.basename(new_file_name)}")
        except Exception as e:
            result['task_count'] += 1
            result['failed_count'] += 1
            result['output_log'].append(f"Error: Failed to rename {os.path.basename(folder_path)}: {str(e)}")
            result['exception'].append(e)
            if console_feedback:
                print(f"Error: Failed to rename {os.path.basename(folder_path)}: {str(e)}")
        return result
    if os.path.isdir(folder_path):
        folder_files = os.listdir(folder_path)
        for file in folder_files:
            try:
                new_file_name = map_function(file)
                new_file_name = os.path.join(folder_path, new_file_name)
                os.rename(os.path.join(folder_path, file), new_file_name)
                result['task_count'] += 1
                result['success_count'] += 1
                result['output_log'].append(f"Info: {file} -> {os.path.basename(new_file_name)}")
                if console_feedback:
                    print(f"{file} -> {os.path.basename(new_file_name)}")
            except Exception as e:
                result['task_count'] += 1
                result['failed_count'] += 1
                result['output_log'].append(f"Error: Failed to rename {file}: {str(e)}")
                result['exception'].append(e)
                if console_feedback:
                    print(f"Error: Failed to rename {file}: {str(e)}")
        return result
    result['output_log'].append(f"Error: Unexpected error")
    if console_feedback:
        print(f"Error: Unexpected error")
    return result