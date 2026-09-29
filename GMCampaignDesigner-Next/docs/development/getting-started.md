# Démarrage développeur

Installer un compilateur C++23, CMake 3.25+, Ninja et une distribution Qt 6 compatible avec les modules déclarés par le build. Copier éventuellement `CMakeUserPresets.json.example`, fournir le préfixe Qt dans son environnement local, puis lancer `cmake --preset debug`, `cmake --build --preset debug` et `ctest --preset debug`.

## Relations

Ne versionnez pas le preset utilisateur; voir [CMake](cmake-guidelines.md) et [structure](repository-structure.md).
