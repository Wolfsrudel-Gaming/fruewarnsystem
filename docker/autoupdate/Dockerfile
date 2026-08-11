FROM docker:27-cli

RUN apk add --no-cache bash git curl jq

COPY update.sh /update.sh
RUN chmod +x /update.sh

CMD ["/update.sh"]
