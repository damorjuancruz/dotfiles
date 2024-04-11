{  pkgs, ... }:

{
  systemd.user.services.ssh-agent = {
    description = "SSH key agent";
    environment = {
      SSH_AUTH_SOCK = "%t/ssh-agent.socket";
      DISPLAY = ":0";
    };
    serviceConfig = {
      ExecStart = "${pkgs.openssh}/bin/ssh-agent -D -a $SSH_AUTH_SOCK";
    };
    wantedBy = ["default.target"];
  };
}
