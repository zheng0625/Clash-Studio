"""Versioned error envelope shared with the Android bridge; preserve legacy detail."""
CODES = {400:'INVALID_REQUEST', 422:'INVALID_REQUEST', 403:'FORBIDDEN', 404:'NOT_FOUND', 409:'CONFLICT',
         413:'LIMIT_EXCEEDED', 428:'PERMISSION_REQUIRED', 429:'BUSY', 501:'UNSUPPORTED',
         502:'CORE_UNCONFIRMED', 503:'UNAVAILABLE', 504:'TIMEOUT'}


def envelope(status, detail, operation_id=None):
    fields = detail if isinstance(detail, dict) else {}
    message = fields.get('message', detail if isinstance(detail, str) else '配置或参数无效')
    error = {'code': fields.get('code', CODES.get(status, 'INTERNAL_ERROR')), 'message': message,
             'retryable': fields.get('retryable', status in (409, 429) or status >= 500),
             'operation_id': fields.get('operation_id') or operation_id}
    if 'rollback' in fields:
        error['rollback'] = fields['rollback']
    return {'detail': detail, 'error': error}
