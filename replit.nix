
{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.python310Packages.pip
    pkgs.python3Packages.fastapi
    pkgs.python3Packages.uvicorn
    pkgs.python3Packages.pydantic
    pkgs.python3Packages.requests
    pkgs.python3Packages.aiofiles
    pkgs.python3Packages.python-multipart
    pkgs.python3Packages.python-dotenv
    pkgs.python3Packages.pyyaml
    pkgs.python3Packages.pymongo
    pkgs.python3Packages.google-cloud-storage
    pkgs.python3Packages.loguru
  ];
}
