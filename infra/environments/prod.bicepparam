using '../main.bicep'

param projectName = 'smartfactory'
param environment = 'prod'
param location = 'koreacentral'
param storageAccountName = 'stsmartfactoryprod001'
param keyVaultName = 'kv-smartfactory-prod'
param eventHubNamespaceName = 'eh-smartfactory-prod'
param eventHubNames = [
  'power-events'
  'anomaly-events'
  'aggregated-power-data'
]
param sqlServerName = ''
param sqlDatabaseName = ''
