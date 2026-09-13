param location string
param serverName string
param databaseName string
param administratorLogin string
@secure()
param administratorLoginPassword string
param tags object = {}

resource sqlServer 'Microsoft.Sql/servers@2021-11-01' = {
  name: serverName
  location: location
  properties: {
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    publicNetworkAccess: 'Disabled'
    minimalTlsVersion: '1.2'
  }
  tags: tags
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2021-11-01' = {
  parent: sqlServer
  name: databaseName
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648
    zoneRedundant: false
  }
  tags: tags
}

output serverId string = sqlServer.id
output databaseId string = sqlDatabase.id
