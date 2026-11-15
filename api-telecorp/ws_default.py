def lambda_handler(event, context):
    # El panel solo escucha; cualquier mensaje recibe "ok"
    return {'statusCode': 200, 'body': 'ok'}
