import sys
import os
import git
import configparser

config_path = os.path.join(os.path.dirname(__file__), "config.ini")


def gitclone(custom_nodes_path, url, target_hash=None):
    repo_name = os.path.splitext(os.path.basename(url))[0]
    repo_path = os.path.join(custom_nodes_path, repo_name)

    # Clone the repository from the remote URL
    repo = git.Repo.clone_from(url, repo_path, recursive=True)

    if target_hash is not None:
        repo.git.checkout(target_hash)
            
    repo.git.clear_cache()
    repo.close()


def gitcheck(path, do_fetch=False):
    try:
        # Fetch the latest commits from the remote repository
        repo = git.Repo(path)

        current_branch = repo.active_branch
        branch_name = current_branch.name

        remote_name = 'origin'
        remote = repo.remote(name=remote_name)

        if do_fetch:
            remote.fetch()

        # Get the current commit hash and the commit hash of the remote branch
        commit_hash = repo.head.commit.hexsha
        remote_commit_hash = repo.refs[f'{remote_name}/{branch_name}'].object.hexsha

        # Compare the commit hashes to determine if the local repository is behind the remote repository
        if commit_hash != remote_commit_hash:
            # Get the commit dates
            commit_date = repo.head.commit.committed_datetime
            remote_commit_date = repo.refs[f'{remote_name}/{branch_name}'].object.committed_datetime

            # Compare the commit dates to determine if the local repository is behind the remote repository
            if commit_date < remote_commit_date:
                print("CUSTOM NODE CHECK: True")
        else:
            print("CUSTOM NODE CHECK: False")
    except Exception as e:
        print(e)
        print("CUSTOM NODE CHECK: Error")


def gitpull(path):
    # Check if the path is a git repository
    if not os.path.exists(os.path.join(path, '.git')):
        raise ValueError('Not a git repository')

    # Pull the latest changes from the remote repository
    repo = git.Repo(path)
    if repo.is_dirty():
        repo.git.stash()

    commit_hash = repo.head.commit.hexsha
    try:
        origin = repo.remote(name='origin')
        origin.pull(rebase=True)
        repo.git.submodule('update', '--init', '--recursive')
        new_commit_hash = repo.head.commit.hexsha

        if commit_hash != new_commit_hash:
            print("CUSTOM NODE PULL: True")
        else:
            print("CUSTOM NODE PULL: None")
    except Exception as e:
        print(e)
        print("CUSTOM NODE PULL: False")

    repo.close()


def checkout_comfyui_hash(target_hash):
    repo_path = os.path.dirname(folder_paths.__file__)

    repo = git.Repo(repo_path)
    commit_hash = repo.head.commit.hexsha

    if commit_hash != target_hash:
        try:
            repo.git.checkout(target_hash)
            print(f"Checked out the ComfyUI: {target_hash}")
        except git.GitCommandError as e:
            print(f"Error checking out the ComfyUI: {str(e)}")


def checkout_custom_node_hash(git_custom_node_infos):
    processed_git_dir = set()

    for path in os.listdir(custom_nodes_path):
        if path.endswith("ComfyUI-Manager"):
            continue

        fullpath = os.path.join(custom_nodes_path, path)

        if os.path.isdir(fullpath):
            is_disabled = path.endswith(".disabled")

            try:
                git_dir = os.path.join(fullpath, '.git')
                if git_dir not in git_custom_node_infos:
                    continue

                need_checkout = False
                item = git_custom_node_infos[git_dir]
                if item['disabled'] and is_disabled:
                    pass
                elif item['disabled'] and not is_disabled:
                    # disable
                    new_path = fullpath + ".disabled"
                    os.rename(fullpath, new_path)
                    pass
                elif not item['disabled'] and is_disabled:
                    # enable
                    new_path = fullpath[:-9]
                    os.rename(fullpath, new_path)
                    processed_git_dir.add(git_dir)
                    need_checkout = True
                else:
                    processed_git_dir.add(git_dir)
                    need_checkout = True

                if need_checkout:
                    repo = git.Repo(fullpath)
                    commit_hash = repo.head.commit.hexsha

                    if commit_hash != item['hash']:
                        repo.git.checkout(item['hash'])
            except Exception as e:
                print(f"Failed to restore snapshots for the custom node '{path}'.\n{e}")

    # clone missing
    for k, v in git_custom_node_infos.items():
        if not v['disabled'] and k not in processed_git_dir:
            path = os.path.dirname(k)
            gitclone(path, k, v['hash'])


def invalidate_custom_node_file(file_custom_node_infos):
    processed_file = set()

    for path in os.listdir(custom_nodes_path):
        if path.endswith("ComfyUI-Manager"):
            continue

        fullpath = os.path.join(custom_nodes_path, path)

        if not os.path.isdir(fullpath) and fullpath.endswith('.py'):
            if path in file_custom_node_infos and file_custom_node_infos[path]['disabled']:
                new_path = fullpath+'.disabled'
                os.rename(fullpath, new_path)

        elif not os.path.isdir(fullpath) and fullpath.endswith('.py.disabled'):
            path = path[:-9]
            if path in file_custom_node_infos and not file_custom_node_infos[path]['disabled']:
                new_path = fullpath[:-9]
                os.rename(fullpath, new_path)
                processed_file.add(path)

    # download missing
    for k, v in file_custom_node_infos.items():
        if k.endswith("ComfyUI-Manager"):
            continue

        if not v['disabled'] and k not in processed_file:
            # TODO: lookup containing extension
            #       install
            pass


def apply_snapshot(target):
    try:
        path = os.path.join(os.path.dirname(__file__), 'snapshots', f"{target}.json")
        if os.path.exists(path):
            info = json.load(path)

            comfyui_hash = info['comfyui']
            git_custom_node_infos = info['git_custom_nodes']
            file_custom_node_infos = info['file_custom_nodes']

            checkout_comfyui_hash(comfyui_hash)
            checkout_custom_node_hash(git_custom_node_infos)
            invalidate_custom_node_file(file_custom_node_infos)

            print("APPLY SNAPSHOT: True")
            return

        print(f"Snapshot file not found: `{path}`")
        print("APPLY SNAPSHOT: False")
    except:
        print(e)
        print("APPLY SNAPSHOT: False")


def setup_environment():
    config = configparser.ConfigParser()
    config.read(config_path)
    if 'default' in config and 'git_exe' in config['default'] and config['default']['git_exe'] != '':
        git.Git().update_environment(GIT_PYTHON_GIT_EXECUTABLE=config['default']['git_exe'])


setup_environment()


try:
    if sys.argv[1] == "--clone":
        gitclone(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "--check":
        gitcheck(sys.argv[2], False)
    elif sys.argv[1] == "--fetch":
        gitcheck(sys.argv[2], True)
    elif sys.argv[1] == "--pull":
        gitpull(sys.argv[2])
    elif sys.argv[1] == "--apply-snapshot":
        apply_snapshot(sys.argv[2])
    sys.exit(0)
except:
    sys.exit(-1)
    
    
