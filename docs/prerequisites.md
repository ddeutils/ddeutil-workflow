# Prerequisites

## Create Public Keys

Start running gen_key.sh file on you local and move it to /home dir for mounting
to SFTP server that was provisioned by the Docker compose.

```shell
ssh-keygen -t ed25519 -f ssh_host_ed25519_key
ssh-keygen -t rsa -b 4096 -f ssh_host_rsa_key
```

## Start Local Services

I create the Docker compose file for provisioning all services that you want to
testing connection.

```shell
docker compose -f .\.container\docker-compose.yml --env-file .\.env up -d
docker compose -f .\.container\docker-compose.yml --env-file .\.env down
```

### SFTP

> [!WARNING]
> This **SFTP** image does not support to login with ssh yet. I will solve this
> problem soon.
> `ssh -i .\mnt\home\ssh_host_ed25519_key -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${SFTP_USER}@127.0.0.1`

```shell
sftp -i .\mnt\home\ssh_host_rsa_key -P 2222 bastion@localhost
```

### Postgres

## Migration Full Service

### SFTP

It can migrate this service to **ACI** (Azure Container Instance) and mount the
data volume to **Azure Storage File Share** (Solution recommend to use
**Azure Blob Storage** because it has the streaming endpoint for video usecase.)

**Prerequisites**:

*   Create **Azure Storage Account**
*   Create **Azure Storage File Share** on above account.
*   Mount File Share to ACI

    ```shell
    az container create \
      --resource-group ${AZ_RG_NAME} \
      --name ${AZ_ACI_NAME} \
      --location southeastasia \
      --image atmoz/sftp:latest \
      --ports 22 \
      --dns-name-label ${AZ_ACI_DNS_NAME} \
      --environment-variables SFTP_USERS=${SFTP_USER}:${SFTP_PASS}:1001 \
      --azure-file-volume-account-name ${AZ_FILE_ACC_NAME} \
      --azure-file-volume-account-key ${AZ_FILE_ACC_KEY} \
      --azure-file-volume-share-name ${AZ_FILE_NAME} \
      --azure-file-volume-mount-path /home/${SFTP_USER}/upload
    ```

> We can access to **ACI** with **FQDN** Protocol, `${AZ_ACI_DNS_NAME}.southeastasia.azurecontainer.io`.
> It will replace from `localhost` to this value.
