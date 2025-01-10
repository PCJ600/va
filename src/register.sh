#!/bin/bash

readonly VA_CONF_DIR=/etc/va
readonly VA_CFG_FILE=${VA_CONF_DIR}/va.cfg

mkdir -p ${VA_CONF_DIR}
touch ${VA_CFG_FILE}
echo "1.0.0.10000" > ${VA_CONF_DIR}/version

function log_info() {
    local log_content=${@:1}
    echo "`date +"%Y-%m-%d %H:%M:%S"` INFO $log_content"
}

function get_va_version() {
    local version=$(cat ${VA_CONF_DIR}/version)
    echo "$version"
}

# record applianceId
function get_appliance_id() {
    local appliance_id=$(cfgapi_readrec "APPLIANCE_ID")
    echo "$appliance_id"
}

function cfgapi_readrec() {
    local name="$1"
    local value=$(grep "^$name" ${VA_CFG_FILE} 2>/dev/null | sed 's/^'"$name"'=//g')
    echo "$value"
    return $?
}

function cfgapi_updrec() {
    local name="$1"
    local value="$2"

    sed -i "/^$name=/d" ${VA_CFG_FILE}
    echo "$name=$value" >> ${VA_CFG_FILE}
}

function do_register() {
    local resp="$1"

    local data=$(cat ${resp} | jq . -cr)
    local appliance_id=$(echo "${data}" | jq .applianceId -cr)
    local token=$(echo "${data}" | jq .applianceToken -cr)
    local iotHost=$(echo "${data}" | jq .iotHost -cr)
    local iotPort=$(echo "${data}" | jq .iotPort -cr)
    log_info "resp data: ${data}, appliance_id: ${appliance_id}, register_token: ${token}, iotHost: ${iotHost}, iotPort: ${iotPort}"

    cfgapi_updrec "APPLIANCE_ID" "${appliance_id}"
    cfgapi_updrec "APPLIANCE_TOKEN" "${token}"
    cfgapi_updrec "IOTHOST" "${iotHost}"
    cfgapi_updrec "IOTPORT" "${iotPort}"
}

function cmd_register() {
    local token=$1
    if [ -z ${token} ]; then
        return 1
    fi

    local host=""
    local customer_id=""
    local version=$(get_va_version)
    local dectoken=$(echo "${token}" | cut -d'.' -f 2 | base64 -d 2>/dev/null)
    if [ -n "${dectoken}" ]; then
        host=$(echo "${dectoken}" | jq .domain -cr)
        cid=$(echo "${dectoken}" | jq .cid -cr)
    fi
    log_info "ready to register, host: ${host}, cid: ${cid}, version: ${version}"
    if [ -z "$host" ] || [ -z "$cid" ]; then
        log_info "missing auth info, exit"
        return 1
    fi
    
    # call register API
    local url="https://$host/va/register/"
    local cpu_num=$(cat /proc/cpuinfo | grep -w processor | wc -l)
    local memory=$(free -b | grep -vw total | head -1 | awk  '{print $2}')
    local storage=$(fdisk -l /dev/sda | grep "Disk /dev/sda" | awk '{print $3}')
    local hostname=$(hostnamectl --static)
    local appliance_id=$(get_appliance_id)
    local ip4addr=$(nmcli con show ens33 | grep IP4.ADDRESS | head -n 1 | awk '{print $2}' | awk -F/ '{print $1}')
    local version=$(get_va_version)
    local localtime=$(date -u +%FT%TZ)
    log_info "cpu: ${cpu_num}, memory: ${memory}, storage: ${storage}, hostname: ${hostname}, appliance_id: ${appliance_id}, ip4addr: ${ip4addr}, localtime: ${localtime}"

    local bodyfile=$(mktemp)
    echo $bodyfile
    echo '{"applianceId":"'$appliance_id'","hostname":"'$hostname'","ipv4Address":"'$ip4addr'","version":"'$version'","registerTime":"'$localtime'","storage":{"used":"0","total":"'$storage'"},"cpu":{"used":"0","total":"'$cpu_num'"},"memory":{"total":"'$memory'"}}' > $bodyfile
    log_info "send register request, req body: $(cat $bodyfile)"

    local ackfile=$(mktemp)
    local errack=$(mktemp)
    local ackcode=`curl -v -s -X POST $url -H "accept: application/json" \
        -H  "Content-Type: application/json" -H "Authorization: Bearer $token" \
        -d @"$bodyfile" --connect-timeout 30 \
        -o $ackfile -w %{http_code} 2>$errack`

    local errmsg="$(cat $errack | grep -v Authorization)"
    local resp_msg="$(cat $ackfile | jq -cr .message)"
    rm -f "$bodyfile" "$errack"
    log_info "register resp MSG: ${resp_msg}"
    if [ "$ackcode" != "200" ]; then
        log_info "register fail, error_msg: ${errmsg}"
        return 1
    fi

    do_register "${ackfile}"
    rm -f ${ackfile}
}

cmd_register "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJjaWQiOiI3N2ExYzk1Ni0xYzhkLTQ3ZmItODAzNi1jOTcwYTRmMmVlNzMiLCJkb21haW4iOiJwZXRlci5iYWNrZW5kLmNvbSIsImV4cCI6MTc2NjM5NzAyOH0.VkMdIjKRQONyy246gylDfUcqE_Be6PTAI4onMesZXRYa3YlnaFib6nOheS2Gze0EPV5EUXYShPoGBVkRdK-42GQCUn0Kw5bFHeRgpde8t2YFxdcNT4gpYwMiKUcUE2EdNI7yyC55kjIpRekjDqsScYzIjktmlSx78vOI9Xaj494jzik5bNpLmNFnVbrkAkKk-oMELEWC4solg-2vY4Gsup2GJIga7SBdP-aIrvGabyv1J6IgxKsUu7rmZyBVSk-Ekg1oig7h2-8qUiQOk6ep8Nam4Dm2KKqwWouWoUm20N6Gy0WEz0-eyez45jFt9UCynz33rv703omtTVGZodmQkA"
