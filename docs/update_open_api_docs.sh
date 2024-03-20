MODE=$1

API_URL_PROD=https://api.vocode.dev/openapi.json
API_URL_LOCAL=http://localhost:3000/openapi.json

if [ "$MODE" == "local" ]; then
  URL=$API_URL_LOCAL
else
  URL=$API_URL_PROD
fi

echo "Updating openapi.json from $URL"
FILE=./openapi.json
curl $URL -o $FILE
npx prettier $FILE --write
npx mintlify dev
