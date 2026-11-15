from utils import avisar_operadores, registrar_historial, tabla


def lambda_handler(event, context):
    # Entrada (json con el task token de Step Functions)
    incidente_id = event['incidente_id']
    fase = event['fase']
    # Proceso: guarda el token; la Step Function queda en pausa hasta que alguien lo use
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente_id},
                                          UpdateExpression='SET task_token = :t, fase = :f',
                                          ExpressionAttributeValues={':t': event['token'], ':f': fase})
    registrar_historial(incidente_id, 'ESPERANDO_' + fase, '', {'tipo': 'INCIDENTE'})
    avisar_operadores({'tipo': 'ACCION_REQUERIDA', 'incidente_id': incidente_id, 'fase': fase})
    # Salida (json)
    return {'statusCode': 200}
