# Prerequisites

## Create Public Keys

Start running gen_key.sh file on you local and move it to /home dir for mounting
to SFTP server that was provisioned by the Docker compose.

```shell
ssh-keygen -t ed25519 -f ssh_host_ed25519_key
ssh-keygen -t rsa -b 4096 -f ssh_host_rsa_key
```

## Start Services

I create the Docker compose file for provisioning all services that you want to
testing connection.

```shell
docker compose -f .\.container\docker-compose.yml --env-file .\.env up -d
docker compose -f .\.container\docker-compose.yml --env-file .\.env down
```

### SFTP

```shell
ssh -i .\mnt\home\ssh_host_ed25519_key bastion@127.0.0.1 -p 2222
```

### Postgres
