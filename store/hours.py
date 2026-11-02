"""Horário de funcionamento (manual, seção 2) e se a loja está aberta agora."""

from datetime import datetime, time, timedelta

# weekday() -> (abertura, fechamento); domingo (6) fechado.
OPENING_HOURS = {
    **{day: (time(9), time(18)) for day in range(5)},
    5: (time(9), time(13)),
}
WEEKDAYS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']


def _next_opening(now: datetime) -> datetime:
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        hours = OPENING_HOURS.get(day.weekday())
        if hours:
            opening = datetime.combine(day, hours[0], tzinfo=now.tzinfo)
            if opening > now:
                return opening
    raise AssertionError('Há pelo menos um dia de funcionamento por semana.')


def store_status(now: datetime) -> dict:
    """Situação da loja no momento. Feriados não estão nos dados e não são considerados."""
    hours = OPENING_HOURS.get(now.weekday())
    status = {'agora': f'{WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y %H:%M}'}
    if hours and hours[0] <= now.time() < hours[1]:
        status.update(aberta=True, fecha_as=hours[1].strftime('%H:%M'))
    else:
        opening = _next_opening(now)
        status.update(
            aberta=False,
            proxima_abertura=f'{WEEKDAYS[opening.weekday()]}, {opening:%d/%m} às {opening:%H:%M}',
        )
    status['observacao'] = 'Feriados não são considerados neste cálculo (a loja fecha em feriados).'
    return status
