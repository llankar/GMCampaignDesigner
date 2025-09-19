import os
from modules.helpers.config_helper import ConfigHelper  # avoid circular import
from modules.helpers.logging_helper import log_function, log_info, log_warning


@log_function
def get_available_models():
    models_path = ConfigHelper.get(
        "Paths",
        "models_path",
        fallback=r"E:\SwarmUI\SwarmUI\Models\Stable-diffusion",
    )
    try:
        models = sorted(
            [
                os.path.splitext(f)[0]
                for f in os.listdir(models_path)
                if f.endswith(".safetensors")
            ]
        )
        log_info(
            f"Discovered {len(models)} SwarmUI models in {models_path}",
            func_name="modules.helpers.swarmui_helper.get_available_models",
        )
        return models
    except Exception as e:
        log_warning(
            f"Failed to load models from {models_path}: {e}",
            func_name="modules.helpers.swarmui_helper.get_available_models",
        )
        return []
