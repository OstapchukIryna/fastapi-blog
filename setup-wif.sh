#!/usr/bin/env bash
# Настройка доступа GitHub Actions к Google Cloud без ключей.
#
# Workload Identity Federation вместо JSON-ключа сервисного аккаунта:
# GitHub выдаёт короткоживущий OIDC-токен на каждый запуск, Google
# обменивает его на доступ. Ключа не существует — значит нечему утечь
# из секретов репозитория и нечего ротировать раз в полгода.
#
# Запускать один раз, локально, с правами владельца проекта.

set -euo pipefail

PROJECT_ID="fastapi-blog-505507"
GITHUB_REPO="OstapchukIryna/fastapi-blog"   # владелец/репозиторий
POOL="github-pool"
PROVIDER="github-provider"
SA_NAME="github-deploy"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# --- Сервисный аккаунт, от имени которого идёт деплой ------------------
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="GitHub Actions deploy" || true

# Ровно то, что нужно для сборки и выкатки, и ничего больше.
# roles/iam.serviceAccountUser — чтобы Cloud Run мог запустить сервис от
# имени своего рантайм-аккаунта.
for role in run.admin artifactregistry.writer iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/${role}" \
    --condition=None >/dev/null
done

# --- Пул и провайдер федерации ----------------------------------------
gcloud iam workload-identity-pools create "$POOL" \
  --location=global \
  --display-name="GitHub Actions" || true

# ! attribute-condition обязателен. Без него токен от любого репозитория
# ! на GitHub подойдёт к этому провайдеру — то есть кто угодно сможет
# ! выкатить свой образ в твой Cloud Run.
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global \
  --workload-identity-pool="$POOL" \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'" || true

# Разрешаем именно этому репозиторию действовать от имени аккаунта.
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${GITHUB_REPO}"

# --- Что положить в секреты репозитория -------------------------------
cat <<EOF

Готово. В GitHub: Settings -> Secrets and variables -> Actions -> New
repository secret, три штуки:

  GCP_PROJECT_ID
    ${PROJECT_ID}

  GCP_SERVICE_ACCOUNT
    ${SA_EMAIL}

  GCP_WIF_PROVIDER
    projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}

Ни один из них не секрет в строгом смысле — это идентификаторы, а не
ключи. Доступ даёт только совпадение репозитория в attribute-condition.
EOF