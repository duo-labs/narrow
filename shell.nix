let
  pkgs = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/3a9e0f239d80fa134e8fcbdee4dfc793902da37e.tar.gz") {};
in

pkgs.stdenv.mkDerivation {
  name = "main";

  buildInputs = [
    pkgs.python38
    pkgs.git
    pkgs.vim
  ];
}
