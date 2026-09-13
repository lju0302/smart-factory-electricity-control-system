using '../main.bicep'

param projectName = 'smartfactory'
param environment = 'dev'
param location = 'koreacentral'
param storageAccountName = 'stsmartfactorydev001'
param keyVaultName = 'kv-smartfactory-dev'
param eventHubNamespaceName = 'eh-smartfactory-dev'
param eventHubNames = [
  'power-events'
  'anomaly-events'
]
param sqlServerName = ''
param sqlDatabaseName = ''
