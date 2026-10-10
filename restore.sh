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

DISPLAY_NAME="$1"
FILE="backup/$DISPLAY_NAME.json"
[ -f "$FILE" ] || { echo "Backup introuvable : $FILE" >&2; exit 1; }

LOG=$(mktemp)
post() { call "$1" "$2" >> "$LOG"; echo >> "$LOG"; }

# 1) Ticket de session (compte technique) pour pouvoir appeler l'API Client
TICKET=$(call Server/LoginWithServerCustomId '{"ServerCustomId":"admin-lookup","CreateAccount":true}' | jq -r '.data.SessionTicket')

# 2) DisplayName -> PlayFabId (seule l'API Client accepte TitleDisplayName)
PLAYFAB_ID=$(curl -sS -X POST "$BASE/Client/GetAccountInfo" \
	-H "Content-Type: application/json" \
	-H "X-Authorization: $TICKET" \
	-d "$(jq -n --arg n "$DISPLAY_NAME" '{TitleDisplayName:$n}')" \
	| jq -r '.data.AccountInfo.PlayFabId')

# 3) Si le joueur n'existe pas : création avec le même CustomId que dans le backup
if [ -z "$PLAYFAB_ID" ] || [ "$PLAYFAB_ID" = "null" ]; then
	CUSTOM_ID=$(jq -r '.userInfo.CustomIdInfo.CustomId // empty' "$FILE")
	[ -z "$CUSTOM_ID" ] && CUSTOM_ID="restored-$(date +%s)"

	LOGIN=$(curl -sS -X POST "$BASE/Client/LoginWithCustomId" \
		-H "Content-Type: application/json" \
		-d "$(jq -n --arg t "$TITLE_ID" --arg c "$CUSTOM_ID" '{TitleId:$t,CustomId:$c,CreateAccount:true}')")
	PLAYFAB_ID=$(printf '%s' "$LOGIN" | jq -r '.data.PlayFabId')
	NEW_TICKET=$(printf '%s' "$LOGIN" | jq -r '.data.SessionTicket')

	if [ -z "$PLAYFAB_ID" ] || [ "$PLAYFAB_ID" = "null" ]; then
		echo "Création impossible : $LOGIN" >&2
		exit 1
	fi

	curl -sS -X POST "$BASE/Client/UpdateUserTitleDisplayName" \
		-H "Content-Type: application/json" \
		-H "X-Authorization: $NEW_TICKET" \
		-d "$(jq -n --arg n "$DISPLAY_NAME" '{DisplayName:$n}')" >> "$LOG"
	echo >> "$LOG"
fi

ID_JSON=$(jq -n --arg id "$PLAYFAB_ID" '{PlayFabId:$id}')

# 4) Statistiques (ForceUpdate ignore les règles d'agrégation Max/Min/Sum)
post Admin/UpdatePlayerStatistics "$(jq -c --arg id "$PLAYFAB_ID" \
	'{PlayFabId:$id, ForceUpdate:true, Statistics:[(.statistics // [])[] | {StatisticName, Value}]}' \
	"$FILE")"

# 5) Player Data : $1 = clé de playerData, $2 = endpoint, $3 = permission (Public/Private, vide pour Internal)
restore_data() {
	local data
	data=$(jq -c --arg k "$1" --arg p "$3" '(.playerData[$k] // {}) | with_entries(select($p == "" or .value.Permission == $p)) | with_entries(.value |= .Value)' "$FILE")
	[ "$data" = "{}" ] && return
	post "$2" "$(jq -n --arg id "$PLAYFAB_ID" --arg p "$3" --argjson d "$data" \
		'{PlayFabId:$id, Data:$d} + (if $p == "" then {} else {Permission:$p} end)')"
}
restore_data data Admin/UpdateUserData Public
restore_data data Admin/UpdateUserData Private
restore_data readOnly Admin/UpdateUserReadOnlyData Public
restore_data readOnly Admin/UpdateUserReadOnlyData Private
restore_data internal Admin/UpdateUserInternalData ""

# 6) Monnaies virtuelles : différence entre l'état actuel et le backup
CURRENT=$(call Admin/GetUserInventory "$ID_JSON")
jq -r --argjson cur "$(printf '%s' "$CURRENT" | jq -c '.data.VirtualCurrency // {}')" '
	(.inventory.VirtualCurrency // empty) as $want
	| ($want + $cur | keys[]) as $k
	| (($want[$k] // 0) - ($cur[$k] // 0)) as $d
	| select($d != 0)
	| "\($k)\t\($d)"' "$FILE" | while IFS=$'\t' read -r k d; do
	if [ "$d" -gt 0 ]; then ep=AddUserVirtualCurrency; else ep=SubtractUserVirtualCurrency; d=$((-d)); fi
	post "Admin/$ep" "$(jq -n --arg id "$PLAYFAB_ID" --arg k "$k" --argjson a "$d" '{PlayFabId:$id, VirtualCurrency:$k, Amount:$a}')"
done

# 7) Bilan : n'affiche que les réponses en erreur
if grep -v -e '"code":200' -e '^$' "$LOG"; then
	echo "Restauration terminée avec des erreurs (voir ci-dessus)" >&2
else
	echo "Restauration OK : $PLAYFAB_ID"
fi
rm -f "$LOG"
