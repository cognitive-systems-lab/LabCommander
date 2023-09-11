
import sys

import click

try:
    from click_help_colors import HelpColorsCommand
    command_cls = HelpColorsCommand
except:
    command_cls = None

from .. import state
from .. import configuration


@click.command(cls=command_cls, short_help="Print current configuration.")
@click.option("--escape", "-e", is_flag=True, help="Escape lines with a hash symbole.")
@click.option("--path", is_flag=True, help="Print path of all configuration paths found.")
def configure(escape, path):
    import toml
    toml_code = toml.dumps(state.config)

    if path:
        config_paths = configuration.get_config_paths()

        for path in config_paths:
            if path.exists():
                prefix = "*"
            else:
                prefix = " "
            print(prefix, path)
        return

    if escape:
        lines = toml_code.splitlines()
        lines = [
            '#' + ln if (ln.strip() and ln[0] not in '#[') else ln
            for ln in lines]
        toml_code = '\n'.join(lines)

    if sys.stdout.isatty():    
        try:
            from pygments import highlight
            from pygments.lexers import TOMLLexer
            from pygments.formatters import Terminal256Formatter
            toml_code = highlight(toml_code, TOMLLexer(), Terminal256Formatter())
            
        except ImportError:
            toml_code

    print(toml_code)
    

"""
def init_config(path=None):
    #Creates a configuration file ~/.config/labc.conf

    # this is only added to activate logging
    # all exceptions are caught because init_config is also called when something is wrong with the configuration
    try:
        load_config()
    except Exception as e:
        print(e)

    with open(default_config_path) as f:
        lines = f.readlines()
    lines = [
        '#' + ln if (ln.strip() and ln[0] not in '#[') else ln
        for ln in lines]

    if where == 'local':
        target_path = local_config_path
    elif where == 'user':
        target_path = user_config_path
    else:
        raise ValueError("Init parameter must be 'local' or 'user'.")

    if user_config_path.exists():
        log.info(f"Reset configuration file {target_path}")
    else:
        log.info(f"Create configuration file {target_path}")
    with open(target_path, 'w') as f:
        f.writelines(lines)"""