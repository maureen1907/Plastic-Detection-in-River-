#cloud-config
package_update: true
packages:
  - docker.io
  - docker-compose
  - curl

runcmd:
  - systemctl enable docker
  - systemctl start docker
  - docker pull ${docker_image}
  - docker run -d --name plastic-api -p 8000:8000 --restart always ${docker_image}

output:
  all: ">> /var/log/cloud-init.log"