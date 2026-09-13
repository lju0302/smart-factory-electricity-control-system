targetScope = 'resourceGroup'

@description('Azure region for the platform resources.')
param location string = resourceGroup().location
@description('Lowercase project identifier used in resource names and tags.')
param projectName string = 'smartfactory'
@description('Deployment environment.')
@allowed([
  'dev'
  'prod'
])
param environment string = 'dev'
@description('Globally unique Storage Account name.')
param storageAccountName string
@description('Globally unique Key Vault name.')
param keyVaultName string
@description('Globally unique Event Hubs namespace name.')
param eventHubNamespaceName string
param eventHubNames array = [
  'power-events'
  'anomaly-events'
]
@description('Optional Azure SQL logical server name. Leave blank to skip SQL creation.')
param sqlServerName string = ''
@description('Optional Azure SQL database name. Leave blank to skip SQL creation.')
param sqlDatabaseName string = ''
@description('SQL administrator login used only when the optional SQL module is enabled.')
param sqlAdminLogin string = 'sqladmin'
@secure()
@description('SQL administrator password. Pass at deployment time; do not store in Git.')
param sqlAdminPassword string = ''
param tags object = {}

var commonTags = union(tags, {
  project: projectName
  environment: environment
  managedBy: 'bicep'
})

resource functionPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${projectName}-functions-${environment}'
  location: location
  kind: 'functionapp'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
  tags: commonTags
}

module storage './modules/storage.bicep' = {
  name: '${projectName}-storage-${environment}'
  params: {
    location: location
    storageAccountName: storageAccountName
    tags: commonTags
  }
}

module monitoring './modules/monitoring.bicep' = {
  name: '${projectName}-monitoring-${environment}'
  params: {
    location: location
    workspaceName: '${projectName}-logs-${environment}'
    appInsightsName: '${projectName}-appi-${environment}'
    tags: commonTags
  }
}

module keyVault './modules/key-vault.bicep' = {
  name: '${projectName}-keyvault-${environment}'
  params: {
    location: location
    keyVaultName: keyVaultName
    tags: commonTags
  }
}

module eventHubs './modules/event-hubs.bicep' = {
  name: '${projectName}-eventhubs-${environment}'
  params: {
    location: location
    namespaceName: eventHubNamespaceName
    eventHubNames: eventHubNames
    tags: commonTags
  }
}

var functionApps = [
  {
    name: 'stream-producer'
    appSettings: [
      {
        name: 'EVENT_HUB_NAME'
        value: eventHubNames[0]
      }
    ]
  }
  {
    name: 'mlforecast'
    appSettings: [
      {
        name: 'EVENT_HUB_NAME'
        value: eventHubNames[0]
      }
    ]
  }
  {
    name: 'anomaly'
    appSettings: [
      {
        name: 'EVENT_HUB_NAME'
        value: eventHubNames[1]
      }
    ]
  }
  {
    name: 'daily-report'
    appSettings: []
  }
  {
    name: 'alert-dispatcher'
    appSettings: [
      {
        name: 'EVENT_HUB_NAME'
        value: eventHubNames[1]
      }
    ]
  }
]

module functionAppModules './modules/function-app.bicep' = [
  for app in functionApps: {
    name: '${projectName}-${app.name}-${environment}'
    params: {
      location: location
      appName: '${projectName}-${app.name}-${environment}'
      planId: functionPlan.id
      storageAccountName: storage.outputs.name
      appSettings: union(app.appSettings, [
        {
          name: 'APP_ENVIRONMENT'
          value: environment
        }
      ])
      tags: commonTags
    }
  }
]

resource eventHubNamespaceExisting 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventHubs.outputs.name
}

resource eventHubReceiverRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for app in functionAppModules: {
    name: guid(eventHubNamespaceExisting.id, app.outputs.principalId, 'event-hubs-data-receiver')
    scope: eventHubNamespaceExisting
    properties: {
      principalId: app.outputs.principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2b629674-e913-4c01-ae53-ef4638e856a1')
    }
  }
]

module sql './modules/sql.bicep' = if (sqlServerName != '' && sqlDatabaseName != '') {
  name: '${projectName}-sql-${environment}'
  params: {
    location: location
    serverName: sqlServerName
    databaseName: sqlDatabaseName
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    tags: commonTags
  }
}

output storageAccountId string = storage.outputs.resourceId
output keyVaultUri string = keyVault.outputs.vaultUri
output eventHubNamespaceId string = eventHubs.outputs.resourceId
output functionAppIds array = [for app in functionAppModules: app.outputs.resourceId]
output functionPrincipalIds array = [for app in functionAppModules: app.outputs.principalId]
