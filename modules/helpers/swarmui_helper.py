import os
from modules.helpers.config_helper import ConfigHelper  # avoid circular import
   
def get_available_models():
    models_path = ConfigHelper.get("Paths", "models_path", fallback=r"E:\SwarmUI\SwarmUI\Models\Stable-diffusion")
    try:
        return sorted([
            os.path.splitext(f)[0]
            for f in os.listdir(models_path)
            if f.endswith(".safetensors")
        ])
    except Exception as e:
        print(f"Failed to load models: {e}")
        return []
