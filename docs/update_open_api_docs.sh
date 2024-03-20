FILE=./openapi.json
curl https://api.vocode.dev/openapi.json -o $FILE
npx prettier $FILE --write
npx mintlify dev
