#!/bin/bash
TITLE_ID=""
SECRET=""
BASE="https://$TITLE_ID.playfabapi.com"

call() {
	local body="${2-}"; [ -z "$body" ] && body='{}'
	curl -sS -X POST "$BASE/$1" \
		-H "Content-Type: application/json" \
		-H "X-SecretKey: $SECRET" \
		-d "$body"
}

mkdir -p backup

DISPLAY_NAME="$1"

# 1) Ticket de session (compte technique) pour pouvoir appeler l'API Client
TICKET=$(call Server/LoginWithServerCustomId '{"ServerCustomId":"admin-lookup","CreateAccount":true}' | jq -r '.data.SessionTicket')

# 2) DisplayName -> PlayFabId (seule l'API Client accepte TitleDisplayName)
PLAYFAB_ID=$(curl -sS -X POST "$BASE/Client/GetAccountInfo" \
	-H "Content-Type: application/json" \
	-H "X-Authorization: $TICKET" \
	-d "$(jq -n --arg n "$DISPLAY_NAME" '{TitleDisplayName:$n}')" \
	| jq -r '.data.AccountInfo.PlayFabId')

if [ -z "$PLAYFAB_ID" ] || [ "$PLAYFAB_ID" = "null" ]; then
	echo "Joueur introuvable pour le Display Name '$DISPLAY_NAME'" >&2
	exit 1
fi

ID_JSON=$(jq -n --arg id "$PLAYFAB_ID" '{PlayFabId:$id}')

# 3) Les 6 appels, dans l'ordre : 0 userInfo, 1 inventory, 2 statistics, 3 data, 4 readOnly, 5 internal
TMP=$(mktemp -d)
i=0
for ep in Admin/GetUserAccountInfo Admin/GetUserInventory Server/GetPlayerStatistics \
          Admin/GetUserData Admin/GetUserReadOnlyData Admin/GetUserInternalData; do
	call "$ep" "$ID_JSON" > "$TMP/$i.json"
	if [ "$(jq -r '.code // empty' "$TMP/$i.json")" != "200" ]; then
		echo "Erreur sur $ep :" >&2
		cat "$TMP/$i.json" >&2; echo >&2
		echo null > "$TMP/$i.json"
	fi
	i=$((i+1))
done

# 4) Assemblage final
jq -s '{
	userInfo:   .[0].data.UserInfo,
	inventory:  .[1].data,
	statistics: .[2].data.Statistics,
	playerData: {data: .[3].data.Data, readOnly: .[4].data.Data, internal: .[5].data.Data}
}' "$TMP"/0.json "$TMP"/1.json "$TMP"/2.json "$TMP"/3.json "$TMP"/4.json "$TMP"/5.json \
	> "backup/$DISPLAY_NAME.json"

rm -rf "$TMP"
