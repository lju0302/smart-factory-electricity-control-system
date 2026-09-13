param location string
param namespaceName string
param eventHubNames array
param tags object = {}

resource namespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource eventHubs 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = [
  for eventHubName in eventHubNames: {
    parent: namespace
    name: eventHubName
    properties: {
      messageRetentionInDays: 1
      partitionCount: 2
    }
  }
]

output resourceId string = namespace.id
output name string = namespace.name
output eventHubIds array = [for i in range(length(eventHubNames)): eventHubs[i].id]
