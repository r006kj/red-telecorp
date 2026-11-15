from utils import ahora_iso, avisar_operadores, registrar_historial, tabla


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    antena_id = event['antena_id']
    fallas = event['fallas']
    # Proceso
    tabla('TABLA_ANTENAS').update_item(Key={'antena_id': antena_id},
                                       UpdateExpression='SET requiere_revision = :r, fallas_7d = :f, marcada_en = :t',
                                       ExpressionAttributeValues={':r': True, ':f': fallas, ':t': ahora_iso()})
    registrar_historial(antena_id, 'PROBLEMA_ESTRUCTURAL',
                        str(fallas) + ' fallas en 7 dias: requiere atencion especializada', {'tipo': 'ANTENA'})
    avisar_operadores({'tipo': 'RECURRENCIA', 'antena_id': antena_id, 'zona_id': event.get('zona_id'), 'fallas': fallas})
    # Salida (json)
    return {'marcada': True}
