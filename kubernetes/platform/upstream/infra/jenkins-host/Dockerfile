FROM jenkins/jenkins:2.585-alpine-jdk21@sha256:e00aee28e0233941e1c952062b2c6f47e44447f8f5a74243dd9ac4e7d7298030
USER root
RUN apk upgrade --no-cache && mkdir -p /opt/phase1-bootstrap && touch /opt/phase1-bootstrap/Jenkinsfile /opt/phase1-bootstrap/Jenkinsfile.publish
USER jenkins
COPY --chown=jenkins:jenkins plugins.lock.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --latest false --plugin-file /usr/share/jenkins/ref/plugins.txt
USER root
# Plugin installation is a build operation; its bundled libraries are not
# needed by the running controller.
RUN rm -f /opt/jenkins-plugin-manager.jar /bin/jenkins-plugin-cli /usr/bin/jenkins-plugin-cli
USER jenkins
ENV CASC_JENKINS_CONFIG=/bootstrap/jenkins.yaml
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"
