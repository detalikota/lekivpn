#!/bin/bash
BOT_TOKEN="8119707163:AAFfeTfkAjL_EgKQcf9zcImD_Lzf-uGyh-g"
CHAT_ID="-1002476639163"
send_telegram_message() {
    message="$1"
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        -d "text=${message}"
}
docker logs -f --tail 100 marzban-marzban-1 2>&1 | while IFS= read -r line; do
    if [[ "$line" == *"error"* ]] || \
       [[ "$line" == *"warning"* ]] || \
       [[ "$line" == *"failed"* ]] || \
       [[ "$line" == *"critical"* ]] || \
       [[ "$line" == *"Unable"* ]]; then
        if [[ "$line" != *"six.reraise"* ]]; then
            send_telegram_message "$line"
        fi
    fi
done

