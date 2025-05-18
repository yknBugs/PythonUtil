from fastmcp import FastMCP
import os
import shutil
import time
import ast
import shlex
import tempfile
import subprocess
import re
import traceback

mcp = FastMCP("Python MCP")

def is_blacklisted_file(abs_path: str) -> bool:
    blacklist = [
        "C:\\Windows\\",
        "C:\\Program Files\\",
        "C:\\Program Files (x86)\\"
    ]

    # blacklist = [
    #     "/etc/",
    # ]

    for black in blacklist:
        if abs_path.startswith(black):
            return True
    return False

def get_formatted_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}b"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f}kb"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f}mb"
    else:
        return f"{size_bytes / (1024 ** 3):.2f}gb"

def try_fix_escapes(code_str: str) -> str:
    """
    Attempt to fix common escape character issues in the provided code string.

    Args:
        code_str (str): The code string to fix.

    Returns:
        str: The fixed code string.
    """
    # Common over-escaping patterns
    fixes = [
        (r'\n', f'\n'),  # Double escaped newlines
        (r'\r', f'\r'),  # Double escaped carriage returns
        (r'\b', f'\b'),  # Double escaped backspaces
        (r'\t', f'\t'),  # Double escaped tabs
        (r'\"', f'\"'),  # Double escaped double quotes
        (r"\'", f"\'"),  # Double escaped single quotes
        (r'\\', f'\\')   # Double escaped backslashes
    ]
    
    # Apply fixes
    fixed_code = code_str
    for pattern, replacement in fixes:
        fixed_code = fixed_code.replace(pattern, replacement)
        
    return fixed_code

def run_code_via_tempfile(code: str, timeout: int) -> str:
    """
    Run the provided Python code via a temporary file and return the output.

    Args:
        code (str): The Python code to execute.
        timeout (int): The timeout for the code execution in seconds.

    Returns:
        str: The result of the code execution.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', encoding='utf-8') as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name
    try:
        # Execute the temporary file
        result = subprocess.run(["python", temp_file_path], capture_output=True, text=True, timeout=timeout)
        output = result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        output = output.replace(temp_file_path, "<stdin>")
        site_pattern = re.compile(r"[a-zA-Z]:[/\\].*?site-packages[/\\]")  # Windows
        # site_pattern = re.compile(r"/.*?/site-packages/")  # Unix-style
        output = site_pattern.sub(r"Python\\lib\\site-packages\\", output)
        return output.strip()
    except subprocess.TimeoutExpired:
        return "[TimeoutError] The code execution took too long and was terminated."
    except Exception as e:
        return f"[ExecutionError] An error occurred while executing the code:\n{traceback.format_exc()}"
    finally:
        os.remove(temp_file_path)

@mcp.tool(name="run-python")
def execute_code(code: str) -> str:
    """
    Run the provided Python code and return the output printed in the console. 
    When performing mathematical calculations or trying to get some other information, 
    remember to import necessary modules at first and call the print function to get the values of variables you want to observe. 
    This tool will also return the time taken to execute the code.

    Args:
        code (str): The Python code to execute.

    Returns:
        str: The result of the code execution.
    """

    start_time = time.time()
    result = ""
    code_to_run = code
    is_harmful = False

    try_fix = False
    fix_reason = ""

    try:
        # Check for potentially harmful operations
        forbidden_patterns = [
            # File write/delete operations
            r"\.write\(", r"\.writelines\(", r"open\([^)]*,[^)]*",
            r"os\.[^\(]*(remove|unlink|rmdir|mkdir|rename|replace)",
            # File operations with 'w', 'a', 'x' modes
            r"with\s+open\([^)]*,[^)]*",  
            # Subprocess calls
            r"subprocess", r"os\.system", r"os\.popen", r"commands\.", 
            r"popen[234]?", r"exec[lvpe]", r"spawn", r"call"
            # Mouse/keyboard simulation
            r"pyautogui", r"pynput", r"mouse", r"keyboard", r"autopy",
            # Dangerous built-ins
            r"(^|\W)(exec|eval)(\W|$)", 
            # Network operations
            r"socket\.", r"urllib", r"requests\.", r"http",
            # Import protections 
            r"__import__\(", r"importlib",
        ]

        # Check for forbidden patterns
        for pattern in forbidden_patterns:
            if re.search(pattern, code_to_run):
                result = result + f"[PermissionError] This code may contain potentially harmful operations. (Regex rule: {pattern})\n"
                is_harmful = True
            
        # Additional AST-based security check
        try:
            parsed_ast = ast.parse(code_to_run)
            for node in ast.walk(parsed_ast):
                # Check for dangerous imports
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name in ['os', 'subprocess', 'shutil', 'sys']:
                            result = result + f"[PermissionError] Importing potentially dangerous modules is not allowed. (Blacklisted module: {name.name})\n"
                            is_harmful = True

                # Check for dangerous import froms
                if isinstance(node, ast.ImportFrom):
                    if node.module in ['os', 'subprocess', 'shutil', 'sys']:
                        result = result + f"[PermissionError] Importing from potentially dangerous modules is not allowed. (Blacklisted module: {node.module})\n"
                        is_harmful = True
        except SyntaxError as e:
            fix_reason = f"[SyntaxError] {str(e)}\n"
            try_fix = True

        if is_harmful:
            result = result + "[Fatal] Execution halted due to potential security risks.\n"
            time_taken = time.time() - start_time
            result += f"[Info] Done. Time elapsed: {time_taken:.3f} seconds."
            return result.strip()
        
        if try_fix:
            # Attempt to fix the code
            try:
                code_to_run = try_fix_escapes(code_to_run)
                ast.parse(code_to_run)
            except SyntaxError as e:
                result = result + fix_reason
                time_taken = time.time() - start_time
                result += f"[Info] Done. Time elapsed: {time_taken:.3f} seconds."
                return result.strip()
            
            result = result + "[Warning] You may have over-escaped your code. The output of your original code is:\n"
            result = result + fix_reason
            result = result + "[Warning] We tried to fix it for you. The output of the fixed code is:\n"
        
        # Execute the code and capture output
        output = run_code_via_tempfile(code_to_run, timeout=30)
        result = result + output
        if len(output) == 0:
            result = result + "[Warning] Code executed successfully with no output. You might forget to print the result."
        result = result + "\n"
        time_taken = time.time() - start_time
        result += f"[Info] Done. Time elapsed: {time_taken:.3f} seconds."
        return result.strip()
    except Exception as e:
        return f"[ServerInternalError] An error occurred while trying to handle your request:\n{traceback.format_exc()}"

@mcp.tool(name="read-file")
def read_file(file_path: str, encoding: str) -> str:
    """
    Read the content of a file and return it as a string.

    Args:
        file_path (str): The path to the file to read. Only accept relative paths.
        encoding (str): The encoding to use when reading the file. Use the same style as Python's open function, e.g., 'utf-8', etc.

    Returns:
        str: The content of the file as a string. 
    """
    try:
        if os.path.isabs(file_path):
            return "[PermissionError] Only relative paths are allowed."
        
        path = os.path.join("D:\\Temp\\TempOutput", file_path) # Limit the file path to a specific directory
        path = os.path.normpath(path)
        
        if is_blacklisted_file(path):
            return "[PermissionError] You do not have permission to access this file."
        
        if "D:\\Temp\\TempOutput" not in path:
            return "[PermissionError] Path traversal attempt detected."
        
        if os.path.normpath(path) == os.path.normpath("D:\\Temp\\TempOutput"):
            return "[SyntaxError] Please specify a file name."
            
        if not os.path.exists(path):
            return "[FileNotFoundError] The file does not exist."
        
        if not os.path.isfile(path):
            return "[FileNotFoundError] The path is not a file."
    
        with open(path, 'r', encoding=encoding) as file:
            content = file.read()
        return content
    except Exception as e:
        return f"[IOException] An error occurred while reading the file:\n{traceback.format_exc()}"

@mcp.tool(name="create-file")
def create_file(file_path: str, content: str, encoding: str) -> str:
    """
    Write content to a new file. If the folder does not exist, it will automatically create this folder.
    So this tool can be also used to create folders, just create an empty file in the folder you want to create and delete it later.

    Args:
        file_path (str): The path to the file to write. Only accept relative paths.
        content (str): The content to write to the file.
        encoding (str): The encoding to use when writing the file. Use the same style as Python's open function, e.g., 'utf-8', etc.

    Returns:
        str: A message indicating success or failure.
    """
    try:
        if os.path.isabs(file_path):
            return "[PermissionError] Only relative paths are allowed."
        
        path = os.path.join("D:\\Temp\\TempOutput", file_path) # Limit the file path to a specific directory
        path = os.path.normpath(path)
        
        if is_blacklisted_file(path):
            return "[PermissionError] You do not have permission to access this file."
        
        if "D:\\Temp\\TempOutput" not in path:
            return "[PermissionError] Path traversal attempt detected."
        
        if os.path.normpath(path) == os.path.normpath("D:\\Temp\\TempOutput"):
            return "[SyntaxError] Please specify a file name."
        
        if os.path.exists(path):
            if os.path.isfile(path):
                return "[FileException] The file already exists. Consider using a different name or deleting this file."
            else:
                return "[FileException] The path is a folder. Consider using a different name or deleting this folder."
            
        # Ensure the directory for the file exists
        result = ""
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
            dir = dir_name.split("\\")[-1]
            result = result + f"[Info] Automatically created directory: {dir}\n"
            
        with open(path, 'w', encoding=encoding) as file:
            file.write(content)

        result = result + f"[Info] Write a {get_formatted_file_size(os.path.getsize(path))} file to {file_path} successfully."
        return result
    except Exception as e:
        return f"[IOException] An error occurred while writing to the file:\n{traceback.format_exc()}"
    
@mcp.tool(name="list-files")
def list_files(directory: str) -> str:
    """
    List all files and folders in a directory.

    Args:
        directory (str): The path to the directory to list. Only accept relative paths. For root directory, use ".".

    Returns:
        str: A string containing the names of the files and folders in the directory.
    """
    try:
        if os.path.isabs(directory):
            return "[PermissionError] Only relative paths are allowed."
        
        path = os.path.join("D:\\Temp\\TempOutput", directory) # Limit the file path to a specific directory
        path = os.path.normpath(path)
        
        if is_blacklisted_file(path):
            return "[PermissionError] You do not have permission to access this folder."
        
        if "D:\\Temp\\TempOutput" not in path:
            return "[PermissionError] Path traversal attempt detected."
        
        if not os.path.exists(path):
            return "[FileNotFoundError] The directory does not exist."
        
        if not os.path.isdir(path):
            return "[FileNotFoundError] The path is not a directory."
    
        files = os.listdir(path)
        result = ""
        for file in files:
            result = result + f"{file}\t"
            file_path = os.path.join(path, file)
            if os.path.isfile(file_path):
                result = result + get_formatted_file_size(os.path.getsize(file_path)) + "\n"
            else:
                result = result + "Folder\n"
        result = result.strip()
        if len(result) == 0:
            result = "[Info] The directory is empty."
        return result
    except Exception as e:
        return f"[IOException] An error occurred while listing the files:\n{traceback.format_exc()}"
    
@mcp.tool(name="delete-file")
def delete_file(target_path: str) -> str:
    """
    Delete a file or folder.

    Args:
        target_path (str): The path to the file or folder to delete. Only accept relative paths.

    Returns:
        str: A message indicating success or failure.
    """
    try:
        if os.path.isabs(target_path):
            return "[PermissionError] Only relative paths are allowed."

        path = os.path.join("D:\\Temp\\TempOutput", target_path)  # Limit the file path to a specific directory
        path = os.path.normpath(path)

        if is_blacklisted_file(path):
            return "[PermissionError] You do not have permission to access this file."

        if "D:\\Temp\\TempOutput" not in path:
            return "[PermissionError] Path traversal attempt detected."
        
        if os.path.normpath(path) == os.path.normpath("D:\\Temp\\TempOutput"):
            return "[PermissionError] You cannot delete the root directory."

        if not os.path.exists(path):
            return "[FileNotFoundError] The file does not exist."

        if os.path.isfile(path):
            size_str = get_formatted_file_size(os.path.getsize(path))
            os.remove(path)
            return f"[Info] Deleted {size_str} {target_path} successfully."
        else:
            shutil.rmtree(path)
            return f"[Info] Deleted folder {target_path} successfully."    
    
    except Exception as e:
        return f"[IOException] An error occurred while deleting the file:\n{traceback.format_exc()}"
    
@mcp.tool(name="run-git-command")
def run_git_command(folder: str, command: str) -> str:
    """
    Run a git command and return the output. 
    Do not directly use git log since it will enter a vim-like interface and stuck forever.
    Consider using -n options to limit the output when using git log.

    Args:
        folder (str): The path to the git repository. Only accept relative paths.
        command (str): The git command to execute. Do NOT omit the "git" prefix.

    Returns:
        str: The output of the git command.
    """
    try:
        if os.path.isabs(folder):
            return "[PermissionError] Only relative paths are allowed."

        path = os.path.join("D:\\Temp\\TempOutput", folder)  # Limit the file path to a specific directory
        path = os.path.normpath(path)

        if is_blacklisted_file(path):
            return "[PermissionError] You do not have permission to access this folder."

        if "D:\\Temp\\TempOutput" not in path:
            return "[PermissionError] Path traversal attempt detected."
        
        if os.path.normpath(path) == os.path.normpath("D:\\Temp\\TempOutput"):
            return "[SyntaxError] Please specify a folder name."
        
        if not os.path.exists(path):
            return "[FileNotFoundError] The folder does not exist."
        
        if not os.path.isdir(path):
            return "[FileNotFoundError] The path is not a folder."
        
        command_tokens = shlex.split(command.strip())
        
        if not command_tokens or "git" != command_tokens[0]:
            return f"[SyntaxError] The command is not a git command. Try to use 'git {command}' instead of '{command}'."

        if any(token in {"&&", ";", "|", "||"} for token in command_tokens):
            return "[PermissionError] You can only use one command at a time."

        if re.search(r'\bgit\s+push\b', command, re.IGNORECASE) or re.search(r'\bgit\s+.*\s+push\b', command):
            return "[PermissionError] This command requires authentication, for security reasons, we do not allow this command."

        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=path, timeout=30)
        result = result.stdout + result.stderr
        result = result.replace("D:/Temp/TempOutput/", "/")
        result = result.strip()

        if "error: pathspec" in result and "'" in command:
            # Automatically fix the quotes from single to double
            result = "[Warning] git only accepts double quotes, but you might use single quotes in your command. The output of your original command is:\n" + result
            new_command = command.replace("'", '"')
            new_result = subprocess.run(new_command, shell=True, capture_output=True, text=True, cwd=path, timeout=30)
            new_result = new_result.stdout + new_result.stderr
            new_result = new_result.replace("D:/Temp/TempOutput/", "/")
            new_result = new_result.strip()
            if len(new_result) == 0:
                new_result = "[Info] The command executed successfully with no output."
            result = result + "\n[Warning] We tried to fix it for you. The fixed command is:\n" + new_command + "\nThe output of the fixed command is:\n" + new_result

        if len(result) == 0:
            return "[Info] The command executed successfully with no output."
        return result
    except subprocess.TimeoutExpired:
        return "[TimeoutError] The command execution took too long and was terminated. Consider adding an -n or -m option."
    except Exception as e:
        return f"[ServerInternalError] An error occurred while trying to handle your request:\n{traceback.format_exc()}"

if __name__ == "__main__":
    # mcp.run(transport="stdio")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=12346, path="/mcp")
