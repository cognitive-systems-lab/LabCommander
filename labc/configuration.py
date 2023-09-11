import logging
from pathlib import Path
from collections.abc import Mapping

import toml
import appdirs

try:
    import coloredlogs
    coloredlogs_available = True
except ImportError:
    coloredlogs_available = False


log = logging.getLogger(__name__)


def get_config_paths(extra_configs=()):
    return [
        Path(__file__).parent / "config.toml",
        # Path(appdirs.site_config_dir()) / "labc/config.toml",
        Path(appdirs.user_config_dir()) / "labc/config.toml",
        Path().absolute() / "config.toml",
        *extra_configs,
    ]


def load_config(extra_configs=()):
    """Load deafault and extra configuration file."""
    
    config_paths = get_config_paths(extra_configs)

    config = ConfDict()
    for path in config_paths:
        if path.exists():
            config.load(path)
        else:
            log.debug(f"{path} does not exists.")
    
    # TODO: move somewhere else
    # set loglevel according to config
    logging.basicConfig()
    level = config["general.loglevel"].upper()
    level = logging.getLevelName(level)
    logging.root.setLevel(level)

    if "coloredlogs" in globals():
        coloredlogs.install(
            level=level,
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s'
        )
        # fmt='%(asctime)s,%(msecs)03d %(hostname)s %(name)s[%(process)d] %(levelname)s %(message)s'
        # coloredlogs.install(level='DEBUG', logger=logger)

    return config
    

class ConfDict(dict):
    """
    Dictionary to store configuration from .toml files.
    
    Lets users access config categories with dot-seperated notations for sub-configuration.

    Example:
    > d = ConfDict({"a": {"b": 1}})
    > d["a.b"]
    1
    """

    @staticmethod
    def _load(file_path):
        
        with open(file_path) as f:
            toml_code = f.read()
        toml_lines = toml_code.split("\n")

        # find key, value pairs defined on the top level
        for i, line in enumerate(toml_lines):
            if line.strip().startswith("["):
                break
        else:
            i += 1

        top_level_keys = (
            line.strip().split("=", maxsplit=1)[0].strip()
            for line in toml_lines[:i]
        )
        top_level_keys = list(filter(bool, top_level_keys))
        
        # find out which lines start with a "[[" or "["
        top_level_dicts = []
        top_level_lists = []
        for line in toml_lines[i:]:
            if line.startswith("[["):
                line = line.split("#")[0].strip()
                key = line[2:-2]
                top_level_lists.append(key)
            elif line.startswith("["):
                line = line.split("#")[0].strip()
                key = line[1:-1]
                top_level_dicts.append(key)
        
        return toml_code, top_level_keys, top_level_dicts, top_level_lists

    def load(self, file_path):
        """
        Update this confdict with other toml file.

        This includes an experimental extetion to TOML regarding the combination 
        of multiple configuration files. Dictionaries defined with brackets ([...])
        will be merged rather then overwritten.
        """

        toml_code, tl_keys, tl_dicts, tl_lists = self._load(file_path)

        new_dict = toml.loads(toml_code, self.__class__)

        for key in tl_keys:
            self[key] = new_dict[key]
        
        for key in tl_dicts:
            if key in self:
                self[key].update(new_dict[key])
            else:
                self[key] = new_dict[key]

        for key in tl_lists:
            if key in self:
                self[key].extend(new_dict[key])
            else:
                self[key] = new_dict[key]
        
    def __getitem__(self, key):
        dict_ = self
        for part in key.split("."):
            dict_ = dict.__getitem__(dict_, part)
        return dict_

    def __contains__(self, key):
        try:
            self.__getitem__(key)
        except KeyError:
            return False
        else:
            return True
