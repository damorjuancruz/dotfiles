{ ... }:

{
  services.syncthing = {
    enable = true;
    user = "jcdamor";
    dataDir = "/home/jcdamor";
    overrideDevices = true;
    overrideFolders = true;
    settings = {
      devices = {
        "phone" = { id = "7MFUHKP-HBCJYYM-FDOL6QB-WAH7I3M-E2DAM3R-ZRNF2AY-QOPYBDC-GI6UXAX"; };
      };
      folders = {
        "documents" = {
          path = "/home/jcdamor/documents";
          devices = ["phone"];
        };
      };
    };
  };
}
