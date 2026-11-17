#!/usr/bin/env python3
"""Assemble the hand-in report and plots from recorded measurements."""
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
import json
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
CHARTS = RESULTS / 'charts'
sys.path.insert(0, str(ROOT))
from load.summarize import summary


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.is_file() else []


def figure(name, title, plot):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10.5, 4.5), layout='constrained')
    ax.set_title(title, fontsize=14, fontweight='bold', loc='left')
    ax.grid(axis='y', color='#d9dee5', alpha=.7)
    plot(ax)
    CHARTS.mkdir(exist_ok=True, parents=True)
    filename = CHARTS / f'{name}.svg'
    fig.savefig(filename, facecolor='white')
    plt.close(fig)
    return f'<img src="{filename.relative_to(ROOT)}" alt="{escape(title)}">'


def missing(reason):
    return f'<p class="missing">{escape(reason)}</p>'


def cell(value):
    if value is None:
        return '—'
    if isinstance(value, float):
        return f'{value:.2f}'
    return escape(str(value))


def table(headers, rows):
    heading = ''.join(f'<th scope="col">{escape(label)}</th>' for label in headers)
    body = ''.join('<tr>'+''.join(f'<td>{cell(value)}</td>' for value in row)+'</tr>' for row in rows)
    return f'<div class="table"><table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>'


def metrics_table(rows):
    return table(['Фаза', 'План', 'Отправлено', 'Готово', 'Отказ', 'Обрыв', 'Тайм-аут',
                  'Не отправлено', 'Ошибка, %', 'Тайм-ауты, %', 'TTFC p50/p95, мс', 'E2E p50/p95, мс'],
                 [(name, s['planned'], s['sent'], s['completed'], s['rejected'], s['aborted'], s['timeout'],
                   s['not_sent'], s['error_fraction']*100 if s['error_fraction'] is not None else None,
                   s['timeout_fraction']*100 if s['timeout_fraction'] is not None else None,
                   ' / '.join(cell(s['ttfc_ms'][q]) for q in ('p50', 'p95')),
                   ' / '.join(cell(s['e2e_ms'][q]) for q in ('p50', 'p95'))) for name, s in rows])


def evidence_a():
    directory = RESULTS / 'a'
    result = read_json(directory / 'summary.json')
    if not result:
        return missing('Итоговый прогон A отсутствует. Команда: make exp-a.')
    times = read_lines(directory/'timeline.jsonl')
    events = {e['event']:e['wall_s'] for e in read_lines(directory/'events.jsonl')}
    requests = {name:read_lines(directory/f'{name}.jsonl') for name in (
        'early','correct','rollout','rollout-long','rollout-version','bad-B','rollback-version','kill-stream','kill-service')}
    def plot(ax):
        palette = {'early':'#bb432a', 'correct':'#16796a', 'rollout':'#356cb3'}
        for stage in palette:
            samples = [v for v in times if v['phase'] == stage and 'pods' in v]
            if not samples:
                continue
            pivot = {'early':'early-upgrade', 'correct':'correct-upgrade', 'rollout':'rollout-start'}[stage]
            t0 = events.get(pivot, samples[0]['wall_s'])
            x = [r['wall_s']-t0 for r in samples]
            def new_pods(row):
                return {p['pod'] for p in row['pods'] if p.get('created') and
                        datetime.fromisoformat(p['created']).timestamp() >= int(t0)}
            ax.step(x, [sum(p['ready'] and p['pod'] in new_pods(r) for p in r['pods']) for r in samples],
                    where='post',color=palette[stage],alpha=.75,label=f'{stage}: новые Ready')
            ax.step(x, [sum(e.get('ready',False) and e['pod'] in new_pods(r) for e in r['endpoints'])
                        for r in samples], color=palette[stage], alpha=.55, linestyle=':', where='post',
                    label=f'{stage}: новые endpoints')
            if stage == 'rollout' and requests['rollout-long']:
                row = requests['rollout-long'][0]
                if row.get('first_wall_s'):
                    ax.plot([row['first_wall_s']-t0,row['completed_wall_s']-t0],[.3,.3],
                            linewidth=5,color='#563b8b',label='Длительный поток')
            elif stage == 'early':
                cold = [r['actual_wall_s']-t0 for r in requests[stage] if r.get('warmed') is False]
                ax.scatter(cold,[.55]*len(cold),marker='x',color=palette[stage],label='Запрос при прогреве')
        ax.axvline(0,color='#202d3f',linestyle='--',linewidth=1)
        ax.set(xlabel='Секунды от начала соответствующего обновления', ylabel='Реплики / endpoints', ylim=(0,3.4))
        ax.legend(loc='best', fontsize=8, ncols=2)
    checks = table(['Проверка', 'Результат'], [(k, 'PASS' if v else 'FAIL') for k,v in result['checks'].items()])
    figs = figure('a-rollout','Прогрев 20 с и rolling update под запросами',plot)
    text = f'''<p>Дефектный режим: {result['early_cold']} запросов приняли до конца прогрева из {result['early_requests']}.
    Исправленный режим: {result['corrected_cold']} из {result['corrected_requests']}.
    Штатный rollout: {result['rollout_requests']} попыток, HTTP 5xx — {result['rollout_5xx']},
    незавершённых — {result['rollout_unfinished']}. При неготовой B выполнено {result['bad_b_requests']} запросов,
    число наблюдавшихся неготовых Pod — {result['bad_b_unready_pods']}.</p>'''
    if requests['rollout-long']:
        stream = requests['rollout-long'][0]
        t0 = events['rollout-start']
        termination = next((r['wall_s'] for r in times if r['phase']=='rollout' and any(
            p['pod']==stream['pod'] and p['terminating'] for p in r.get('pods',[]))),None)
        if termination is not None and stream['first_wall_s'] is not None:
            text += (f'<p>Поток {escape(stream["request_id"])} на {escape(stream["pod"])} отдал первую часть '
                     f'в {stream["first_wall_s"]-t0:+.1f} с от начала обновления. Первое наблюдение '
                     f'Terminating у этого Pod — {termination-t0:+.1f} с. Последняя отметка клиента — '
                     f'{stream["completed_wall_s"]-t0:+.1f} с, получено {stream["parts"]} частей.</p>')
    if result['kill_requests']:
        stream = result['kill_requests'][0]
        t0 = events.get('forced-process-exit')
        if t0 is not None:
            ready = next((r['wall_s'] for r in times if r['phase']=='kill' and r['wall_s']>t0 and any(
                p['pod']==stream['pod'] and p['ready'] and p['restarts']>0 for p in r.get('pods',[]))),None)
            restart = next((r['wall_s'] for r in times if r['phase']=='kill' and r['wall_s']>t0 and any(
                p['pod']==stream['pod'] and p['restarts']>0 for p in r.get('pods',[]))),None)
            text += (f'<p>Клиент аварийного запроса получил {stream["parts"]} частей из {stream["requested_parts"]}; '
                     f'результат {escape(stream["outcome"])} через {stream["completed_wall_s"]-t0:.1f} с от команды выхода. '
                     f'Остальной трафик: {result["during_kill_success"]} успешных.</p>')
            if ready and restart:
                text += f'<p>Restart замечен через {restart-t0:.1f} с, этот Pod снова Ready через {ready-t0:.1f} с.</p>'
    return text + figs + metrics_table([(n,summary(rs)) for n,rs in requests.items()]) + checks


def evidence_b():
    trials = read_json(RESULTS/'b/summary.json', [])
    if not trials:
        return missing('Длинные серии B пока не записаны. Команда: make exp-b.')
    groups = defaultdict(list)
    for trial in trials:
        data = trial['trial']
        groups[data['policy'],data['profile']].append(trial)
    def plot_breakdown(ax):
        selected = [t for t in trials if t['trial']['profile']=='skew80']
        labels, values, queues = [], [], []
        for trial in selected:
            pods = sorted(trial['by_pod'].values(),key=lambda pod:pod['planned'],reverse=True)
            for rank, pod in enumerate(pods):
                labels.append(f"{trial['trial']['trial'].replace('-skew80','')}\nPod {rank+1} (N={pod['planned']})")
                values.append(pod['ttfc_ms']['p95'] or 0)
                queues.append(pod['queue_ms']['p95'] or 0)
        x = range(len(labels))
        ax.bar([i-.2 for i in x], values, width=.40,label='TTFC p95',color='#356cb3')
        ax.bar([i+.2 for i in x], queues, width=.40,label='Очередь p95',color='#cf6541')
        ax.set(xlabel='Прогоны skew80 и Pod по убыванию трафика',ylabel='мс',xticks=list(x),xticklabels=labels)
        ax.tick_params(axis='x',labelsize=7)
        ax.legend()
    def plot_policy(ax):
        for i, profile in enumerate(('uniform','skew80')):
            for j, policy in enumerate(('ordinary','affinity')):
                trials_in_group = groups.get((policy,profile),[])
                x = i+(j-.5)*.36
                if not trials_in_group:
                    continue
                p95 = [t['all']['ttfc_ms']['p95'] for t in trials_in_group if t['all']['ttfc_ms']['p95'] is not None]
                if not p95:
                    continue
                color = ('#356cb3','#cf6541')[j]
                ax.bar(x,median(p95),width=.3,color=color,alpha=.55,label=policy if i==0 else None)
                ax.scatter([x+.07*(k-(len(p95)-1)/2) for k in range(len(p95))],p95,color=color,zorder=3)
        ax.set(xlabel='Профиль нагрузки и политика (столбец — медиана p95, точка — прогон)',
               ylabel='Клиентский TTFC p95, мс',xticks=[0,1],xticklabels=['Равномерно','80% через один IP'])
        ax.legend()
    overview = metrics_table([(t['trial']['trial'],t['all']) for t in trials])
    per_pod = []
    for trial in trials:
        for pod, data in sorted(trial['by_pod'].items()):
            per_pod.append((trial['trial']['trial'],pod,data['planned'], data['completed'], data['rejected'],
                            data['queue_ms']['p95'],data['ttfc_ms']['p95'],data['cache_hits'],data['cache_misses']))
    plots = figure('b-pods','Хвост задержки и ожидание по репликам',plot_breakdown) + figure('b-policy','Политики Service при одинаковом расписании',plot_policy)
    ready = sum(t['trial'].get('duration_s',0)>=120 for t in trials)
    headline = f'<p>Завершены {len(trials)} из 12 серий. Серий длительностью не менее 120 с: {ready}.</p>'
    aggregate = []
    for (policy, profile), items in sorted(groups.items()):
        success = sum(t['all']['completed'] for t in items)
        sent = sum(t['all']['sent'] for t in items)
        p95s = [t['all']['ttfc_ms']['p95'] for t in items if t['all']['ttfc_ms']['p95'] is not None]
        aggregate.append((profile,policy,len(items),success,100*(sent-success)/sent if sent else None,
                          median(p95s) if p95s else None, sum(t['all']['cache_hits'] for t in items),
                          sum(t['all']['cache_misses'] for t in items)))
    skew = {row[1]: row for row in aggregate if row[0]=='skew80' and row[2]>=3}
    if {'ordinary','affinity'} <= skew.keys():
        ordinary, affinity = skew['ordinary'],skew['affinity']
        headline += (f'<p>При 80% трафика с одного IP медиана p95 TTFC составила {cell(affinity[5])} мс '
                     f'у ClientIP и {cell(ordinary[5])} мс у обычного Service. Доля ошибок в трёх сериях '
                     f'составила {cell(affinity[4])}% и {cell(ordinary[4])}% соответственно. '
                     f'Обычный Service дал {ordinary[6]} попаданий и {ordinary[7]} промахов среди '
                     f'успешных запросов, ClientIP — {affinity[6]} и {affinity[7]}. Цена сброса '
                     'привязки в этом опыте ограничена шестью повторяющимися ключами в кеше на 16 записей.</p>')
    analysis = read_json(RESULTS/'b/analysis.json',{})
    actual_routes = []
    for records in analysis.values():
        for entry in records:
            actual_routes.append((entry['trial'],
                                  ' / '.join(str(p['requests']) for p in entry['pods'].values()),
                                  100*entry['max_pod_share'] if entry['max_pod_share'] is not None else None,
                                  entry['send_late_p95_ms'],entry['occupancy']['waiting_while_another_idle_samples'],
                                  ', '.join(entry['source_ips'])))
    return (headline+plots+table(['Профиль','Service','Прогоны','Готово','Ошибка, %','Медиана p95, мс','Hit','Miss'],aggregate)
            + overview + table(['Прогон','Pod','Попытки','Готово','Отказы','Очередь p95, мс','TTFC p95, мс','Hit','Miss'],per_pod)
            + (table(['Прогон','Запросы по Pod','Макс. доля, %','Отставание клиента p95, мс',
                      'Очередь при свободном соседе, отсчёты по 100 мс','IP источников'],actual_routes) if actual_routes else ''))


def evidence_c():
    directory = RESULTS/'c'
    phases = read_json(directory/'summary.json', [])
    timeline = read_lines(directory/'timeline.jsonl')
    observations = read_json(directory/'observations.json', {})
    if not phases or not timeline:
        return missing('Итоговый прогон C отсутствует. Команда: make exp-c.')
    begin = timeline[0]['ts_wall_s']
    sent = Counter(int((row['actual_wall_s']-begin)//5) for row in read_lines(directory/'requests.jsonl')
                   if row.get('actual_wall_s') is not None)

    def plot(ax):
        x = [row['ts_wall_s']-begin for row in timeline]
        ready = [sum((pod['ready'] or {}).get('status') == 'True' and not pod['deleting']
                     for pod in row['pods']) for row in timeline]
        desired = [row['hpa'].get('desiredReplicas') for row in timeline]
        cpu = [next((item.get('resource',{}).get('current',{}).get('averageUtilization')
                     for item in row['hpa'].get('currentMetrics',[]) if item.get('type') == 'Resource'), None)
               for row in timeline]
        ax.step(x,ready,where='post',label='Ready',color='#16796a')
        ax.step(x,desired,where='post',linestyle=':',label='Желаемые HPA',color='#356cb3')
        ax.set(xlabel='Секунды от начала наблюдения',ylabel='Количество реплик',ylim=(0.8,3.5))
        traffic = ax.twinx()
        for index, phase in enumerate(phases):
            start = phase['start_at_unix_s']-begin
            end = phase['stop_dispatch_at_unix_s']-begin
            traffic.plot([start,end],[phase['rps']]*2,color='#cf6541',linewidth=3,
                         label='Расписание, запрос/с' if index==0 else None)
        if sent:
            bins = range(int((timeline[-1]['ts_wall_s']-begin)//5)+1)
            traffic.plot([5*i+2.5 for i in bins],[sent[i]/5 for i in bins],color='#8a4931',
                         linewidth=1,linestyle='--',label='Фактически отправлено, окна 5 с')
        traffic.set(ylabel='Нагрузка, запрос/с',ylim=(0,30))
        lines, labels = ax.get_legend_handles_labels()
        extra, extra_labels = traffic.get_legend_handles_labels()
        ax.legend(lines+extra,labels+extra_labels,loc='upper left',fontsize=8)
        if any(v is not None for v in cpu):
            inset = ax.inset_axes([0.69,0.12,0.29,0.27])
            inset.plot(x,cpu,color='#795582',linewidth=1)
            inset.axhline(60,linestyle=':',color='#aaa')
            inset.set_title('CPU HPA, % request',fontsize=8); inset.tick_params(labelsize=7)

    transitions = [(field,r['phase'],r['ts_wall_s']-begin,r['replicas'])
                   for field in ('desired','ready') for r in observations.get(f'{field}_changes',[])]
    alerts = [(name,r['phase'],r['ts_wall_s']-begin,r['state'])
              for name, rr in observations.get('alerts',{}).items() for r in rr]
    histogram = read_json(directory/'histograms.json', {})
    comparison = []
    for phase,item in histogram.items():
        for server, client in (('ttfc','ttfc_ms'),('duration','e2e_ms')):
            def extract(field):
                result = item[server][field].get('data',{}).get('result',[])
                return float(result[0]['value'][1]) if result else None
            client_stats = item['client_same_completion_window'][client]
            estimate = extract('p95')
            comparison.append((phase,server,client_stats['n'],client_stats['p95'],extract('samples'),
                               estimate*1000 if estimate is not None else None))
    exact = read_json(directory/'histograms-quiet-edges.json',{})
    edge_comparison = []
    for phase, item in exact.items():
        for server, client in (('hw11_ttfc_seconds','ttfc_ms'),('hw11_request_duration_seconds','e2e_ms')):
            values = item['prometheus'][server]
            n = values['samples']['result']
            estimate = values['p95_seconds']['result']
            count = float(n[0]['value'][1]) if n else None
            p95 = 1000*float(estimate[0]['value'][1]) if estimate else None
            edge_comparison.append((phase,client,item['client'][client]['n'],item['client'][client]['p95'],count,p95))
    pod_times = []
    for name, seen in observations.get('first_seen_pods',{}).items():
        first_ready = observations.get('first_ready_pods',{}).get(name)
        elapsed = (datetime.fromisoformat(first_ready)-datetime.fromisoformat(seen['created'])).total_seconds() if first_ready else None
        pod_times.append((name,seen['created'],first_ready,elapsed))
    captions = []
    desired = observations.get('desired_changes',[])
    up = next((x for x in desired if x['replicas']==3), None)
    down = next((x for x in desired if up and x['replicas']==2 and x['ts_wall_s']>up['ts_wall_s']),None)
    if up and down:
        recovery = next((p['start_at_unix_s'] for p in phases if p['name']=='recover-scale-down'),None)
        if recovery:
            captions.append(f'Снижение: {down["ts_wall_s"]-recovery:.1f} с от начала спокойной фазы до желаемых двух реплик, включая ожидание актуальных CPU-метрик.')
    for phase in phases:
        if phase['name'] not in ('hot-scale-up','overload-alerts'):
            continue
        by_pod = phase['summary']['by_pod']
        captions.append(f'{phase["name"]}: '+', '.join(f'{k} — {v["planned"]}' for k,v in by_pod.items())+' попыток с известным Pod.')
    return (figure('c-hpa','Реплики, нагрузка и CPU при HPA',plot)
            + ''.join(f'<p>{escape(c)}</p>' for c in captions)
            + metrics_table([(p['name'],p['summary']['all']) for p in phases])
            + table(['Метрика','Фаза','t, с','Реплик'],transitions)
            + table(['Pod','Создан (UTC)','Ready (UTC)','Прогрев и запуск, с'],pod_times)
            + table(['Алерт','Фаза','t, с','Состояние'],alerts)
            + '<p>Сравнение по окну завершения и PromQL <code>increase</code>; дробное N отражает экстраполяцию между scrape.</p>'
            + table(['Фаза','Длительность','N клиент','p95 клиент, мс','N scrape','p95 PromQL, мс'],comparison)
            + ('<p>Сравнение по снимкам счётчиков на тихих границах фаз.</p>'
               +table(['Фаза','Длительность','N клиент','p95 клиент, мс','N scrape','p95 PromQL, мс'],edge_comparison) if edge_comparison else ''))


def write_requests():
    phases = ['early','correct','rollout','rollout-long','rollout-version','bad-B','rollback-version',
              'kill-stream','kill-service','session-a','session-b','session-a-after']
    paths = [('A',RESULTS/'a'/f'{phase}.jsonl') for phase in phases]
    paths += [('B',path) for path in sorted((RESULTS/'b').glob('*-r[0-9]/requests.jsonl'))]
    paths += [('C',path) for path in sorted((RESULTS/'c').rglob('requests*.jsonl'))]
    with (RESULTS/'requests.jsonl').open('w') as stream:
        for name,path in paths:
            for row in read_lines(path):
                item = {'experiment':name,'source':str(path.relative_to(RESULTS)),**row}
                stream.write(json.dumps(item,ensure_ascii=False)+'\n')


def main():
    template = (ROOT/'report-template.html').read_text()
    write_requests()
    values = {'@A@':evidence_a(), '@B@':evidence_b(), '@C@':evidence_c()}
    for token, content in values.items():
        template = template.replace(token,content)
    (ROOT/'report.html').write_text(template)


if __name__=='__main__':
    main()
