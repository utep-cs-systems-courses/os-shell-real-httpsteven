#!/usr/bin/env python3

import os
import sys
import re

def print_prompt():
    ps1 = os.getenv("PS1", "$ ")
    print(ps1, end="", flush=True)

def get_status_info(status):
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return None

def fork_and_execute(command, setup=None, cleanup=None):
    try:
        pid = os.fork()
        if pid == 0:  # Child process
            if setup:
                setup()
            os.execve(command[0], command, os.environ)
        elif pid > 0:  # Parent process
            if cleanup:
                cleanup()
            _, status = os.waitpid(pid, 0)
            return get_status_info(status)
    except FileNotFoundError:
        sys.stderr.write(f"{command[0]}: command not found\n")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")

def find_executable(command):
    if os.path.isabs(command[0]) and os.access(command[0], os.X_OK):
        return command
    paths = os.getenv("PATH", "").split(":")
    for path in paths:
        executable_path = os.path.join(path, command[0])
        if os.path.exists(executable_path) and os.access(executable_path, os.X_OK):
            return [executable_path] + command[1:]
    return command

def redirect_input(input_file):
    fd = open(input_file, 'r')
    os.dup2(fd.fileno(), sys.stdin.fileno())
    fd.close()

def redirect_output(output_file):
    fd = open(output_file, 'w')
    os.dup2(fd.fileno(), sys.stdout.fileno())
    fd.close()

def pipe_commands(command1, command2):
    read_end, write_end = os.pipe()
    setup_command1 = lambda: (os.dup2(write_end, sys.stdout.fileno()), os.close(read_end))
    cleanup_command1 = lambda: os.close(write_end)
    setup_command2 = lambda: (os.dup2(read_end, sys.stdin.fileno()), os.close(write_end))
    cleanup_command2 = lambda: os.close(read_end)

    status1 = fork_and_execute(command1, setup_command1, cleanup_command1)
    status2 = fork_and_execute(command2, setup_command2, cleanup_command2)
    return status2

def execute_background(command):
    try:
        pid = os.fork()
        if pid == 0:
            os.setsid()
            os.umask(0)
            os.execve(command[0], command, os.environ)
        else:
            print(f"[{pid}] Started in background")
            return pid
    except Exception as e:
        sys.stderr.write(f"Error executing background task: {e}\n")

def process_command(command, redirect_in=None, redirect_out=None, background=False, piped=False):
    if redirect_in:
        return fork_and_execute(command, setup=lambda: redirect_input(redirect_in))
    if redirect_out:
        return fork_and_execute(command, setup=lambda: redirect_output(redirect_out))
    if background:
        return execute_background(command)
    if piped:
        return pipe_commands(piped[0], command)
    return fork_and_execute(command)

def handle_special_commands(args):
    if args[0] == "cd":
        try:
            os.chdir(args[1])
        except FileNotFoundError:
            print(f"cd: {args[1]}: No such file or directory")
        except IndexError:
            print("cd: missing operand")
        return True
    return False

def main():
    while True:
        print_prompt()
        user_input = input().strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue
        
        commands = re.split(r'\s*\|\s*', user_input)
        for i, command_str in enumerate(commands):
            args = command_str.split()
            if not args:
                continue

            redirect_in = next((args[i+1] for i, x in enumerate(args) if x == "<"), None)
            redirect_out = next((args[i+1] for i, x in enumerate(args) if x == ">"), None)
            background = args[-1] == "&"
            if background:
                args = args[:-1]

            if handle_special_commands(args):
                continue

            command = find_executable(args)
            prev_command = process_command(command, redirect_in, redirect_out, background, piped=prev_command if i > 0 else None)

if __name__ == "__main__":
    main()#! /usr/bin/env python3

import os
import sys
import re

def print_prompt():
    ps1 = os.getenv("PS1", "$ ")
    print(ps1, end="", flush=True)

def execute_command(command):
    try:
        pid = os.fork()
        if pid == 0:  # Child process
            os.execve(command[0], command, os.environ)
        elif pid > 0:  # Parent process
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                if os.WEXITSTATUS(status) != 0:
                    print(f"Program terminated with exit code {os.WEXITSTATUS(status)}")
    except Exception:
        print(f"{command[0]}: command not found")
        sys.exit(1)

def find_command(command):
    if os.path.isabs(command[0]) and os.access(command[0], os.X_OK):
        return command
    paths = os.getenv("PATH", "").split(":")
    for path in paths:
        executable_path = os.path.join(path, command[0])
        if os.path.exists(executable_path) and os.access(executable_path, os.X_OK):
            return [executable_path] + command[1:]
    return command

def handle_input_redirection(command, input_file):
    try:
        pid = os.fork()
        if pid == 0:
            with open(input_file, 'r') as f:
                os.dup2(f.fileno(), sys.stdin.fileno())
                os.execve(command[0], command, os.environ)
        elif pid > 0:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        return 1
    except Exception as e:
        print(f"Error: {e}")

def handle_output_redirection(command, output_file):
    try:
        pid = os.fork()
        if pid == 0:
            with open(output_file, 'w') as f:
                os.dup2(f.fileno(), sys.stdout.fileno())
                os.execve(command[0], command, os.environ)
        elif pid > 0:
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
    except PermissionError:
        print(f"Error: Cannot write to output file '{output_file}'")
        return 1
    except Exception as e:
        print(f"Error: {e}")

def handle_piping(command1, command2):
    try:
        pipe_read, pipe_write = os.pipe()
        pid1 = os.fork()
        if pid1 == 0:
            os.dup2(pipe_write, sys.stdout.fileno())
            os.close(pipe_read)
            os.close(pipe_write)
            os.execve(command1[0], command1, os.environ)
        elif pid1 > 0:
            os.close(pipe_write)
            pid2 = os.fork()
            if pid2 == 0:
                os.dup2(pipe_read, sys.stdin.fileno())
                os.close(pipe_read)
                os.execve(command2[0], command2, os.environ)
            elif pid2 > 0:
                os.close(pipe_read)
                _, status1 = os.waitpid(pid1, 0)
                _, status2 = os.waitpid(pid2, 0)
                if os.WIFEXITED(status1) and os.WIFEXITED(status2):
                    return os.WEXITSTATUS(status2)
    except Exception as e:
        print(f"Error: {e}")

def execute_background_task(command):
    try:
        pid = os.fork()
        if pid == 0:
            os.setsid()
            os.umask(0)
            try:
                os.execve(command[0], command, os.environ)
            except FileNotFoundError:
                sys.stderr.write(f"{command[0]}: command not found\n")
                sys.exit(1)
        else:
            print(f"[{pid}] Started in background")
            return pid
    except Exception as e:
        sys.stderr.write(f"Error executing background task: {e}\n")

def main():
    current_directory = os.getcwd()
    while True:
        print_prompt()
        user_input = input().strip()
        if user_input.lower() == "exit":
            break
        if not user_input:  # Ignore completely empty input
            continue
        
        # Split the input into commands using pipes and process each separately
        pipe_commands = re.split(r'\s*\|\s*', user_input)
        prev_command = None
        command = None
        
        for i, command_str in enumerate(pipe_commands):
            command_str = command_str.strip()  # Trim whitespace around the command
            if not command_str:  # If the command is empty after stripping, skip it
                continue
            
            args = command_str.split()
            if not args:  # Additionally check if splitting results in an empty list
                continue

            input_file = None
            output_file = None
            if '<' in args:
                input_index = args.index('<')
                input_file = args[input_index + 1]
                del args[input_index:input_index + 2]

            if '>' in args:
                output_index = args.index('>')
                output_file = args[output_index + 1]
                del args[output_index:output_index + 2]

            if args[0] == 'cd':
                try:
                    if len(args) > 1 and args[1] == '..':
                        current_directory = os.path.dirname(current_directory)
                    else:
                        current_directory = os.path.abspath(args[1])
                    os.chdir(current_directory)
                except FileNotFoundError:
                    print(f"cd: {args[1]}: No such file or directory")
            elif i == 0:
                command = find_command(args)
                if input_file:
                    handle_input_redirection(command, input_file)
                elif output_file:
                    handle_output_redirection(command, output_file)
                elif command[-1] == "&":
                    execute_background_task(command[:-1])
                else:
                    execute_command(command)
            else:
                command = find_command(args)
                if prev_command:
                    handle_piping(prev_command, command)
            prev_command = command

if __name__ == "__main__":
    main()
