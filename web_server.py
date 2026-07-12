import os
import threading
from flask import Flask, render_template, request, send_file, Response, make_response
from flask_socketio import SocketIO, emit, disconnect
import socket
import config
import database

state_lock = threading.RLock()

# --- Flask 設定 ---
PORT = 5003
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=5, ping_interval=2)

# --- 內部 SSL 通道設定 (保持與原 app.py 一致) ---
USE_SSL = False
INTERNAL_SCHEME = "http"

def get_gui():
    """動態載入並獲取 GUI 實體，避免循環引用 (Circular Import)"""
    try:
        import gui_main
        return gui_main.PoomsaeReplicaGUI.instance
    except Exception as e:
        print(f"無法取得 GUI 單例實體: {e}")
        return None


@app.route('/')
def index():
    return render_template('judge.html')

@app.route('/cert.pem')
def serve_cert():
    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cert.pem')
    if os.path.exists(cert_path):
        return send_file(cert_path, mimetype='application/x-x509-ca-cert', as_attachment=True, download_name='cert.pem')
    return "Certificate not found", 404

@app.route('/static/nosleep.mp4')
def serve_nosleep_video():
    """提供支援 HTTP Range Requests 的 nosleep.mp4，讓 iOS Safari 能正確請求並播放靜音影片以防止螢幕休眠。"""
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'nosleep.mp4')
    if not os.path.exists(video_path):
        return "nosleep.mp4 not found", 404

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range', None)

    if range_header:
        # 解析 Range: bytes=start-end
        byte_range = range_header.replace('bytes=', '')
        parts = byte_range.split('-')
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        with open(video_path, 'rb') as f:
            f.seek(start)
            data = f.read(length)

        resp = make_response(data, 206)
        resp.headers['Content-Type'] = 'video/mp4'
        resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)
        resp.headers['Cache-Control'] = 'no-cache'
        return resp
    else:
        resp = make_response(open(video_path, 'rb').read(), 200)
        resp.headers['Content-Type'] = 'video/mp4'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(file_size)
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

@app.route('/api/start_scoring')
def api_start_scoring():
    player_name = request.args.get('player', 'TEST PLAYER')
    try: mode = int(request.args.get('mode', 0))
    except: mode = 0
    try: stage = int(request.args.get('stage', 1))
    except: stage = 1
    try: player_side = int(request.args.get('player_side', 0))
    except: player_side = 0
    try: pk_sequence_mode = int(request.args.get('pk_sequence_mode', 0))
    except: pk_sequence_mode = config.system_settings.get('pk_sequence_mode', 0)
    
    team = request.args.get('team', '')
    no = request.args.get('no', '')
    category = request.args.get('category', '')
    division = request.args.get('division', '')
    phase = request.args.get('phase', '')
    poomsae_name = request.args.get('poomsae', '')
    poomsae_1 = request.args.get('poomsae_1', '')
    poomsae_2 = request.args.get('poomsae_2', '')
    match_type = request.args.get('match_type', '')
    chung_player = request.args.get('chung_player', '')
    chung_team = request.args.get('chung_team', '')
    hong_player = request.args.get('hong_player', '')
    hong_team = request.args.get('hong_team', '')
    
    payload = {
        'player': player_name,
        'team': team,
        'no': no,
        'mode': mode,
        'stage': stage,
        'category': category,
        'division': division,
        'phase': phase,
        'poomsae': poomsae_name,
        'poomsae_1': poomsae_1,
        'poomsae_2': poomsae_2,
        'match_type': match_type,
        'chung_player': chung_player,
        'chung_team': chung_team,
        'hong_player': hong_player,
        'hong_team': hong_team,
        'player_side': player_side,
        'pk_sequence_mode': pk_sequence_mode
    }
    
    # 更新當前打分方位到全域狀態，供大螢幕投影讀取
    with state_lock:
        config.current_state['current_player_side'] = player_side
        
        # 每次開始新一輪評分前，重設所有裁判的 submitted 狀態與分數，避免上一步段狀態殘留
        for sid, jd in config.current_state['judges'].items():
            if player_side == 0:
                # 新一場比賽開始（評分青方）：清空青方與紅方的分數，重置所有 submitted 狀態
                jd['submitted'] = False
                jd['chung_submitted'] = False
                jd['hong_submitted'] = False
                jd['acc'] = 0.0
                jd['pres'] = 0.0
                jd['p1'] = 0.0
                jd['p2'] = 0.0
                jd['p3'] = 0.0
                jd['total'] = 0.0
                jd['hong_acc'] = 0.0
                jd['hong_pres'] = 0.0
                jd['hong_p1'] = 0.0
                jd['hong_p2'] = 0.0
                jd['hong_p3'] = 0.0
                jd['hong_total'] = 0.0
                jd['freestyle_scores'] = {}
            else:
                # 切換至紅方：只重置紅方的 submitted 與分數，保留青方的分數與 submitted 狀態
                jd['submitted'] = False
                jd['hong_submitted'] = False
                jd['hong_acc'] = 0.0
                jd['hong_pres'] = 0.0
                jd['hong_p1'] = 0.0
                jd['hong_p2'] = 0.0
                jd['hong_p3'] = 0.0
                jd['hong_total'] = 0.0
        
        config.current_state['is_scoring'] = True
    config.current_state['current_player_payload'] = payload
    if mode == 1 and pk_sequence_mode == 0:
        # PK 同時上場：發送專屬雙挹2面PK介面事件
        socketio.emit('pk_scoring_start', payload, namespace='/')
    else:
        # 一般賽制，或 PK 交叉/依序上場（裁判端使用一般評分介面，但payload含 player_side 讓裁判平板顯示提示）
        socketio.emit('scoring_start', payload, namespace='/')
    return "OK"

@app.route('/api/stop_scoring')
def api_stop_scoring():
    final_score = request.args.get('final_score', '')
    rank = request.args.get('rank', '')
    stop_scoring(final_score, rank)
    return "OK"

@app.route('/api/resume_scoring')
def api_resume_scoring():
    config.current_state['is_scoring'] = True
    config.current_state.pop('last_stop_data', None)  # 評分徵復，清除上次結果紀錄
    socketio.emit('scoring_resume', namespace='/')
    return "OK"

@app.route('/api/reset_match')
def api_reset_match():
    with state_lock:
        config.current_state['is_scoring'] = False
        config.current_state.pop('last_stop_data', None)  # 重置比賳，清除上次結果紀錄
        for sid, jd in config.current_state['judges'].items():
            jd['submitted'] = False
            jd['chung_submitted'] = False
            jd['hong_submitted'] = False
            jd['acc'] = 4.0
            jd['pres'] = 6.0
            jd['p1'] = 2.0
            jd['p2'] = 2.0
            jd['p3'] = 2.0
            jd['total'] = 10.0
            jd['hong_acc'] = 4.0
            jd['hong_pres'] = 6.0
            jd['hong_p1'] = 2.0
            jd['hong_p2'] = 2.0
            jd['hong_p3'] = 2.0
            jd['hong_total'] = 10.0
            jd['freestyle_scores'] = {}
    socketio.emit('reset_match')
    return "OK"

@app.route('/api/timer_sync')
def api_timer_sync():
    seconds = request.args.get('seconds', '90')
    running = request.args.get('running', '0')
    socketio.emit('timer_sync', {'seconds': int(seconds), 'running': int(running) == 1})
    return "OK"

@app.route('/api/test_pk')
def api_test_pk():
    """臨時測試路由：用來觸發 PK 同時上場的裁判評分介面"""
    config.current_state['is_scoring'] = True
    payload = {
        'match_type': '公認品勢',
        'category': '親子雙人品勢',
        'division': '配對組',
        'phase': 'A組',
        'stage': 1,
        'poomsae_1': '太極一章 Taegeuk1',
        'chung_team': '新平武跆拳道館',
        'chung_player': '游羽恩/游輝平',
        'hong_team': '台北市隊',
        'hong_player': '王大明/李小明'
    }
    socketio.emit('pk_scoring_start', payload, namespace='/')
    return "已發送 PK 同時上場測試訊號！請查看裁判平板畫面。"

def broadcast_connected_judges():
    with state_lock:
        connected = []
        for sid, jd in config.current_state['judges'].items():
            if jd.get('connected', False) and not jd.get('id', '').startswith('manual_'):
                connected.append(jd.get('id'))
    socketio.emit('connected_judges_update', {'connected': list(set(connected))}, namespace='/')

@socketio.on('connect')
def handle_connect():
    broadcast_connected_judges()

@socketio.on('join_judge')
def handle_join(data):
    judge_name = data.get('judge_id', 'Unknown')
    sid = request.sid
    
    # 限制僅允許符合設定中開放人數的裁判連入
    try:
        judge_count = int(config.system_settings.get("judge_count", 5))
        if judge_name.startswith('J'):
            judge_num = int(judge_name[1:])
            if judge_num > judge_count:
                emit('join_rejected', {'reason': 'judge_limit_exceeded', 'judge_id': judge_name, 'max_judges': judge_count}, to=sid)
                return
    except Exception as e:
        print(f"限制連入判定異常: {e}")
    
    with state_lock:
        existing_judge = None
        existing_sid = None
        for old_sid, jd in list(config.current_state['judges'].items()):
            if jd.get('id') == judge_name and not old_sid.startswith('manual_'):
                existing_judge = jd
                existing_sid = old_sid
                break
                
        gui = get_gui()
        if existing_judge:
            if existing_judge.get('kicked', False):
                config.current_state['judges'].pop(existing_sid, None)
                emit('force_disconnect', {}, to=sid)
                return
                
            if existing_judge.get('connected', False) and existing_sid != sid:
                # iOS 裝置（如 iPad）重新整理時可能不會馬上斷開舊 Socket，
                # 為了避免裁判被卡在登入畫面，當偵測到同名登入時，主動踢除舊連線，由新連線接管。
                emit('force_disconnect', {}, to=existing_sid)
                disconnect(sid=existing_sid)
                print(f"[{judge_name}] 偵測到重複登入，舊連線 ({existing_sid}) 已被強制斷開，由新連線接管。")
                
            config.current_state['judges'].pop(existing_sid, None)
            config.current_state['judges'][sid] = existing_judge
            config.current_state['judges'][sid]['connected'] = True
            
            mode = gui.mode_var.get() if gui else 0
            stage = gui.current_stage if gui else 1
            pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
            current_side = config.current_state.get('current_player_side', 0)
            
            emit('reconnect_state', {
                'is_scoring': config.current_state['is_scoring'],
                'accuracy': existing_judge.get('acc', 4.0),
                'presentation': existing_judge.get('pres', 6.0),
                'p1': existing_judge.get('p1', 2.0),
                'p2': existing_judge.get('p2', 2.0),
                'p3': existing_judge.get('p3', 2.0),
                'hong_accuracy': existing_judge.get('hong_acc', 4.0),
                'hong_presentation': existing_judge.get('hong_pres', 6.0),
                'hong_p1': existing_judge.get('hong_p1', 2.0),
                'hong_p2': existing_judge.get('hong_p2', 2.0),
                'hong_p3': existing_judge.get('hong_p3', 2.0),
                'submitted': existing_judge.get('submitted', False),
                'chung_submitted': existing_judge.get('chung_submitted', False),
                'hong_submitted': existing_judge.get('hong_submitted', False),
                'pk_sequence_mode': pk_seq,
                'current_player_side': current_side,
                'mode': mode,
                'stage': stage,
                'freestyle_scores': existing_judge.get('freestyle_scores', {}),
                'player_payload': config.current_state.get('current_player_payload'),
                'timer_seconds': gui.timer_seconds if gui else 90,
                'timer_running': gui.timer_running if gui else False,
                'last_stop_data': config.current_state.get('last_stop_data'),
                'projection_slide_data': config.current_state.get('projection_slide_data')  # 用於還原最終結果畫面
            }, to=sid)
        else:
            config.current_state['judges'][sid] = {
                'id': judge_name, 
                'acc': 4.0, 
                'pres': 6.0, 
                'p1': 2.0,
                'p2': 2.0,
                'p3': 2.0,
                'total': 10.0, 
                'hong_acc': 4.0,
                'hong_pres': 6.0,
                'hong_p1': 2.0,
                'hong_p2': 2.0,
                'hong_p3': 2.0,
                'hong_total': 10.0,
                'submitted': False,
                'connected': True,
                'freestyle_scores': {}
            }
            
        emit('status_update', {
            'is_scoring': config.current_state['is_scoring'],
            'tournament_name': config.system_settings.get('tournament_name', '品勢評分賽事'),
            'court_no': config.system_settings.get('court_no', 1)
        }, to=sid)

        projection_slide_data = config.current_state.get('projection_slide_data')
        if projection_slide_data:
            emit('projection_slide_changed', projection_slide_data, to=sid)
        
        if not existing_judge and config.current_state['is_scoring'] and config.current_state.get('current_player_payload'):
            payload = config.current_state['current_player_payload']
            pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
            payload_mode = payload.get('mode', 0)
            is_pk_simultaneous = (payload_mode == 1 and pk_seq == 0)
            if is_pk_simultaneous:
                # PK 同時上場：裁判端使用雙側 PK 介面
                emit('pk_scoring_start', payload, to=sid)
            else:
                # 一般賽制 / PK 交叉依序上場：裁判端使用一般評分介面
                emit('scoring_start', payload, to=sid)
            if gui:
                emit('timer_sync', {
                    'seconds': gui.timer_seconds,
                    'running': gui.timer_running
                }, to=sid)
                
    if gui:
        gui.root.after(0, gui.refresh_judge_slots)
    broadcast_connected_judges()

@socketio.on('modify_score')
def handle_modify():
    sid = request.sid
    with state_lock:
        if sid in config.current_state['judges']:
            jd = config.current_state['judges'][sid]
            jd['submitted'] = False
            jd['acc'] = 0.0
            jd['pres'] = 0.0
            jd['p1'] = 0.0
            jd['p2'] = 0.0
            jd['p3'] = 0.0
            jd['total'] = 0.0
            gui = get_gui()
            if gui:
                gui.root.after(0, gui.refresh_judge_slots)
                gui.root.after(0, check_all_submitted)

@socketio.on('submit_score')
def handle_score(data):
    sid = request.sid
    with state_lock:
        if not config.current_state['is_scoring']: return
        if sid in config.current_state['judges']:
            jd = config.current_state['judges'][sid]
            
            current_side = config.current_state.get('current_player_side', 0)
            mode = config.current_state.get('current_player_payload', {}).get('mode', 0)
            pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
            
            if mode == 1 and (pk_seq == 1 or pk_seq == 2) and current_side == 1:
                # PK交叉/依序上場：紅方評分，儲存至 hong_ 系列欄位
                jd['hong_acc'] = float(data.get('accuracy', 0))
                jd['hong_pres'] = float(data.get('presentation', 0))
                jd['hong_p1'] = float(data.get('p1', 0.0))
                jd['hong_p2'] = float(data.get('p2', 0.0))
                jd['hong_p3'] = float(data.get('p3', 0.0))
                jd['hong_total'] = jd['hong_acc'] + jd['hong_pres']
                jd['pk_mode'] = 'sequence'
                jd['hong_submitted'] = True
            else:
                # 一般賽制或 PK 交叉/依序上場的青方評分，儲存至一般欄位
                jd['acc'] = float(data.get('accuracy', 0))
                jd['pres'] = float(data.get('presentation', 0))
                jd['p1'] = float(data.get('p1', 0.0))
                jd['p2'] = float(data.get('p2', 0.0))
                jd['p3'] = float(data.get('p3', 0.0))
                jd['total'] = jd['acc'] + jd['pres']
                jd['pk_mode'] = 'sequence' if (mode == 1 and (pk_seq == 1 or pk_seq == 2)) else 'normal'
                jd['chung_submitted'] = True

            jd['submitted'] = True
            check_all_submitted()

@socketio.on('pk_submit_score')
def handle_pk_score(data):
    """PK 同時上場：裁判一次送出青方（player_side=0）與紅方（player_side=1）的分數"""
    sid = request.sid
    
    with state_lock:
        if not config.current_state['is_scoring']: return
        if sid not in config.current_state['judges']: return
        
        jd = config.current_state['judges'][sid]
        chung_data = data.get('chung', {})
        hong_data  = data.get('hong', {})
        
        # 儲存青方分數（以 player_side=0 標記）
        jd['acc']  = float(chung_data.get('accuracy', 0))
        jd['pres'] = float(chung_data.get('presentation', 0))
        jd['p1']   = float(chung_data.get('p1', 0.0))
        jd['p2']   = float(chung_data.get('p2', 0.0))
        jd['p3']   = float(chung_data.get('p3', 0.0))
        jd['total'] = round(jd['acc'] + jd['pres'], 1)
        
        # 額外儲存紅方分數，供主控台匯總使用
        jd['hong_acc']  = float(hong_data.get('accuracy', 0))
        jd['hong_pres'] = float(hong_data.get('presentation', 0))
        jd['hong_p1']   = float(hong_data.get('p1', 0.0))
        jd['hong_p2']   = float(hong_data.get('p2', 0.0))
        jd['hong_p3']   = float(hong_data.get('p3', 0.0))
        jd['hong_total'] = round(jd['hong_acc'] + jd['hong_pres'], 1)
        
        jd['submitted'] = True
        jd['pk_mode'] = 'simultaneous'
        
        check_all_submitted()



@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    with state_lock:
        if sid in config.current_state['judges']:
            config.current_state['judges'][sid]['connected'] = False
    gui = get_gui()
    if gui:
        gui.root.after(0, gui.refresh_judge_slots)
    broadcast_connected_judges()

@socketio.on('leave_judge')
def handle_leave():
    sid = request.sid
    with state_lock:
        if sid in config.current_state['judges']:
            config.current_state['judges'].pop(sid, None)
    gui = get_gui()
    if gui:
        gui.root.after(0, gui.refresh_judge_slots)
    broadcast_connected_judges()

def kick_invalid_judges():
    judge_count = int(config.system_settings.get("judge_count", 5))
    
    with state_lock:
        sids_to_remove = []
        for sid, data in config.current_state['judges'].items():
            jid_str = data.get('id', '')
            judge_num = 0
            if jid_str.startswith('J'):
                try: judge_num = int(jid_str[1:])
                except: pass
            elif jid_str.startswith('manual_J'):
                try: judge_num = int(jid_str[8:])
                except: pass
                
            if judge_num > judge_count:
                sids_to_remove.append(sid)
                
        for sid in sids_to_remove:
            socketio.emit('force_disconnect', {}, to=sid)
            config.current_state['judges'].pop(sid, None)
        
    gui = get_gui()
    if gui:
        gui.root.after(0, gui.refresh_judge_slots)


def check_all_submitted():
    if not config.current_state['judges']: return
    gui = get_gui()
    if gui:
        gui.root.after(0, _check_all_submitted_main_thread)

def _check_all_submitted_main_thread():
    with state_lock:
        if not config.current_state['judges']: return
        judges_snapshot = {
            sid: jdata.copy()
            for sid, jdata in config.current_state['judges'].items()
        }
    
    required_judges = int(config.system_settings["judge_count"])
    gui = get_gui()
    if not gui: return
    
    unique_judges = {}
    for sid, jdata in judges_snapshot.items():
        jid = jdata.get('id', '')
        if not jid:
            continue
        if jid not in unique_judges or sid.startswith("manual_"):
            unique_judges[jid] = jdata
            
    active_judges = list(unique_judges.values())
    submitted_judges = [j for j in active_judges if j['submitted']]
    wait_threshold = required_judges 
    
    gui.update_live_scores()

    if len(submitted_judges) >= wait_threshold:
        gui.update_button_states() 
        current_side = config.current_state.get('current_player_side', 0)
        mode = gui.mode_var.get() if hasattr(gui, 'mode_var') else 0
        pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
        
        if mode == 1 and pk_seq in [1, 2] and current_side == 1:
            # 紅方評分時，從暫存區取得青方當前回合的正確分數
            chung_acc_list = []
            chung_pres_list = []
            if hasattr(gui, 'temp_scores_to_save'):
                scores_for_round = gui.temp_scores_to_save.get(gui.current_stage, [])
                for s in scores_for_round:
                    if s.get('player_side') == 0:
                        chung_acc_list.append(s.get('acc', 0.0))
                        chung_pres_list.append(s.get('pres', 0.0))
            
            if chung_acc_list:
                acc_list = chung_acc_list
                pres_list = chung_pres_list
            else:
                acc_list = [0.0] * len(submitted_judges)
                pres_list = [0.0] * len(submitted_judges)
        else:
            acc_list = [j['acc'] for j in submitted_judges]
            pres_list = [j['pres'] for j in submitted_judges]
        
        def calc_avg(scores):
            if not scores: return 0.0
            if len(scores) <= 3: return sum(scores) / len(scores)
            else:
                scores_only = list(scores)
                scores_only.sort()
                valid = scores_only[1:-1]
                return sum(valid) / len(valid)

        avg_acc = calc_avg(acc_list)
        avg_pres = calc_avg(pres_list)
        
        try: deduction = float(gui.lbl_deduction_val.cget("text"))
        except: deduction = 0.0

        final_score = avg_acc + avg_pres - deduction
        
        avg_acc = round(avg_acc, 2)
        avg_pres = round(avg_pres, 2)
        final_score = round(final_score, 3) 
        
        sum_acc = round(sum(acc_list), 2)
        sum_pres = round(sum(pres_list), 2)
        raw_sum = round(sum_acc + sum_pres, 2)

        gui.temp_avg_acc = avg_acc
        gui.temp_avg_pres = avg_pres
        gui.temp_raw_sum = raw_sum

        gui.update_final_score(f"{final_score:.3f}")
        gui.center_stats_labels["Total_L_0"].config(text=f"{sum_acc:.1f}")
        gui.center_stats_labels["Total_L_1"].config(text=f"{sum_pres:.1f}")
        gui.center_stats_labels["Total_L_2"].config(text=f"{raw_sum:.1f}")
        
        gui.center_stats_labels["Avg_L_0"].config(text=f"{avg_acc:.2f}")
        gui.center_stats_labels["Avg_L_1"].config(text=f"{avg_pres:.2f}")
        gui.center_stats_labels["Avg_L_2"].config(text=f"{final_score:.3f}")
        
        mode = gui.mode_var.get()
        if mode == 1:
            deduction_R = 0.0
            # 判斷紅方是否已經有成績 (如果有任一裁判送出紅方成績，或是在同時上場模式下)
            has_hong_score = any(j.get('hong_acc', 0.0) > 0 for j in submitted_judges)
            
            if has_hong_score:
                # PK 賽制：計算紅方的分數
                hong_acc_list = [j.get('hong_acc', 0.0) for j in submitted_judges]
                hong_pres_list = [j.get('hong_pres', 0.0) for j in submitted_judges]
                
                hong_avg_acc = calc_avg(hong_acc_list)
                hong_avg_pres = calc_avg(hong_pres_list)
                
                try: deduction_R = float(gui.lbl_deduction_val_R.cget("text"))
                except: deduction_R = 0.0
                
                hong_final_score = hong_avg_acc + hong_avg_pres - deduction_R
                
                hong_avg_acc = round(hong_avg_acc, 2)
                hong_avg_pres = round(hong_avg_pres, 2)
                hong_final_score = round(hong_final_score, 3)
                
                hong_sum_acc = round(sum(hong_acc_list), 2)
                hong_sum_pres = round(sum(hong_pres_list), 2)
                hong_raw_sum = round(hong_sum_acc + hong_sum_pres, 2)
                
                gui.center_stats_labels["Total_R_0"].config(text=f"{hong_sum_acc:.1f}")
                gui.center_stats_labels["Total_R_1"].config(text=f"{hong_sum_pres:.1f}")
                gui.center_stats_labels["Total_R_2"].config(text=f"{hong_raw_sum:.1f}")
                
                gui.center_stats_labels["Avg_R_0"].config(text=f"{hong_avg_acc:.2f}")
                gui.center_stats_labels["Avg_R_1"].config(text=f"{hong_avg_pres:.2f}")
                gui.center_stats_labels["Avg_R_2"].config(text=f"{hong_final_score:.3f}")
                
                gui.lbl_final_R.config(text=f"{hong_final_score:.3f}")
                if hasattr(gui, 'update_right_panel_scores'):
                    gui.update_right_panel_scores(hong_avg_acc, hong_avg_pres, deduction_R, hong_final_score, hong_raw_sum)
            else:
                for r_key in ["Total", "Avg"]:
                    for c_idx in range(3):
                        gui.center_stats_labels[f"{r_key}_R_{c_idx}"].config(text="")
                gui.lbl_final_R.config(text="-")
        else:
            for r_key in ["Total", "Avg"]:
                for c_idx in range(3):
                    gui.center_stats_labels[f"{r_key}_R_{c_idx}"].config(text="")
            gui.lbl_final_R.config(text="") 
        
        gui.update_left_panel_scores(avg_acc, avg_pres, deduction, final_score, raw_sum)
        
        if gui.current_match_data:
            match_uuid = gui.current_match_uuid
            cat = gui.current_match_data["Category"]
            current_side = config.current_state.get('current_player_side', 0)
            round_num = gui.current_stage
            
            if 'temp_scores' not in config.current_state:
                config.current_state['temp_scores'] = {}
                
            scores_list = config.current_state['temp_scores'].get(round_num, [])
            pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
            
            if mode == 1 and pk_seq == 0:
                # PK 賽制 (同時上場)：同時儲存青方與紅方的分數到暫存區 (全部覆寫)
                scores_list = []
                chung_name = gui.current_match_data.get("C_Name", "")
                hong_name = gui.current_match_data.get("H_Name", "")
                for j in submitted_judges:
                    scores_list.append({
                        'match_uuid': match_uuid, 'category': cat, 'player_name': chung_name,
                        'judge_id': j['id'], 'acc': j['acc'], 'pres': j['pres'], 'total': j['total'],
                        'round_num': round_num, 'p1': j.get('p1', 0.0), 'p2': j.get('p2', 0.0), 'p3': j.get('p3', 0.0),
                        'deduction': deduction, 'player_side': 0
                    })
                    scores_list.append({
                        'match_uuid': match_uuid, 'category': cat, 'player_name': hong_name,
                        'judge_id': j['id'], 'acc': j.get('hong_acc', 0.0), 'pres': j.get('hong_pres', 0.0),
                        'total': j.get('hong_total', 0.0), 'round_num': round_num,
                        'p1': j.get('hong_p1', 0.0), 'p2': j.get('hong_p2', 0.0), 'p3': j.get('hong_p3', 0.0),
                        'deduction': deduction_R, 'player_side': 1
                    })
            elif mode == 1 and pk_seq in [1, 2]:
                # PK 賽制 (交叉/依序)：只覆寫當前方位的分數
                scores_list = [s for s in scores_list if s['player_side'] != current_side]
                if current_side == 0:
                    chung_name = gui.current_match_data.get("C_Name", "")
                    for j in submitted_judges:
                        scores_list.append({
                            'match_uuid': match_uuid, 'category': cat, 'player_name': chung_name,
                            'judge_id': j['id'], 'acc': j['acc'], 'pres': j['pres'], 'total': j['total'],
                            'round_num': round_num, 'p1': j.get('p1', 0.0), 'p2': j.get('p2', 0.0), 'p3': j.get('p3', 0.0),
                            'deduction': deduction, 'player_side': 0
                        })
                else:
                    hong_name = gui.current_match_data.get("H_Name", "")
                    for j in submitted_judges:
                        scores_list.append({
                            'match_uuid': match_uuid, 'category': cat, 'player_name': hong_name,
                            'judge_id': j['id'], 'acc': j.get('hong_acc', 0.0), 'pres': j.get('hong_pres', 0.0),
                            'total': j.get('hong_total', 0.0), 'round_num': round_num,
                            'p1': j.get('hong_p1', 0.0), 'p2': j.get('hong_p2', 0.0), 'p3': j.get('hong_p3', 0.0),
                            'deduction': deduction_R, 'player_side': 1
                        })
            else:
                # 一般賽制
                scores_list = [s for s in scores_list if s['player_side'] != current_side]
                if current_side == 1 and gui.current_match_data.get("Game") == 1:
                    p_name = gui.current_match_data.get("H_Name", "")
                else:
                    p_name = gui.current_match_data.get("C_Name", "")
                    
                for j in submitted_judges:
                    scores_list.append({
                        'match_uuid': match_uuid,
                        'category': cat,
                        'player_name': p_name,
                        'judge_id': j['id'],
                        'acc': j['acc'],
                        'pres': j['pres'],
                        'total': j['total'],
                        'round_num': round_num,
                        'p1': j.get('p1', 0.0),
                        'p2': j.get('p2', 0.0),
                        'p3': j.get('p3', 0.0),
                        'deduction': deduction,
                        'player_side': current_side
                    })
            config.current_state['temp_scores'][round_num] = scores_list
            gui.temp_scores_to_save[round_num] = scores_list # 為了相容性保留
            
            with open("debug_scores.log", "a", encoding="utf-8") as f:
                import json
                f.write(f"Round: {round_num}, Side: {current_side}, Scores: {json.dumps(scores_list, ensure_ascii=False)}\n")

    else:
        gui.update_button_states()
        gui.update_final_score("")
        gui.clear_left_panel_scores(gui.current_stage)
        
        for r_key in ["Total", "Avg"]:
            for side in ["L", "R"]:
                for c_idx in range(3):
                    label_key = f"{r_key}_{side}_{c_idx}"
                    if label_key in gui.center_stats_labels:
                        gui.center_stats_labels[label_key].config(text="")
        gui.lbl_final_R.config(text="")

def calc_pk_history_scores():
    gui = get_gui()
    if not gui or not gui.current_match_uuid:
        return {}
    
    match_uuid = gui.current_match_uuid
    rows = []
    temp_scores = config.current_state.get('temp_scores', getattr(gui, 'temp_scores_to_save', {}))
    if temp_scores:
        for r_num, scores_list in temp_scores.items():
            for s in scores_list:
                if s.get('match_uuid') == match_uuid:
                    rows.append((
                        s['round_num'],
                        s.get('player_side', 0),
                        s['acc'],
                        s['pres'],
                        s['deduction'],
                        s['total']
                    ))
                    
    if not rows:
        try:
            import sqlite3
            import database
            conn = sqlite3.connect(database.get_db_path())
            c = conn.cursor()
            c.execute("""
                SELECT round, player_side, accuracy, presentation, deduction, total
                FROM scores
                WHERE match_uuid = ?
            """, (match_uuid,))
            rows = c.fetchall()
            conn.close()
        except:
            rows = []
            
    scores_by_grp = {}
    for row in rows:
        r_num, side, acc, pres, ded, tot = row
        grp_key = (r_num, side)
        if grp_key not in scores_by_grp:
            scores_by_grp[grp_key] = {'acc': [], 'pres': [], 'total': [], 'ded': []}
        scores_by_grp[grp_key]['acc'].append(acc)
        scores_by_grp[grp_key]['pres'].append(pres)
        scores_by_grp[grp_key]['total'].append(tot)
        scores_by_grp[grp_key]['ded'].append(ded)
        
    def calc_avg(scores):
        if not scores: return 0.0
        if len(scores) <= 3: return sum(scores) / len(scores)
        scores_only = list(scores)
        scores_only.sort()
        valid = scores_only[1:-1]
        return sum(valid) / len(valid)
        
    def calc_group_metrics(grp_data):
        if not grp_data: return {'total': 0.0}
        accs = grp_data['acc']
        press = grp_data['pres']
        deds = grp_data['ded']
        
        avg_acc = calc_avg(accs)
        avg_pres = calc_avg(press)
        deduction = max(deds) if deds else 0.0
        final = avg_acc + avg_pres - deduction
        return {'total': final}
        
    chung_1r = calc_group_metrics(scores_by_grp.get((1, 0)))
    chung_2r = calc_group_metrics(scores_by_grp.get((2, 0)))
    hong_1r  = calc_group_metrics(scores_by_grp.get((1, 1)))
    hong_2r  = calc_group_metrics(scores_by_grp.get((2, 1)))
    
    chung_final = 0.0
    if chung_1r['total'] > 0 and chung_2r['total'] > 0:
        chung_final = (chung_1r['total'] + chung_2r['total']) / 2
    elif chung_1r['total'] > 0:
        chung_final = chung_1r['total']
        
    hong_final = 0.0
    if hong_1r['total'] > 0 and hong_2r['total'] > 0:
        hong_final = (hong_1r['total'] + hong_2r['total']) / 2
    elif hong_1r['total'] > 0:
        hong_final = hong_1r['total']
        
    return {
        'chung_1r': round(chung_1r['total'], 3),
        'chung_2r': round(chung_2r['total'], 3),
        'chung_final': round(chung_final, 3),
        'hong_1r': round(hong_1r['total'], 3),
        'hong_2r': round(hong_2r['total'], 3),
        'hong_final': round(hong_final, 3)
    }

def stop_scoring(final_score="", rank=""):
    config.current_state['is_scoring'] = False
    
    gui = get_gui()
    mode = gui.mode_var.get() if gui else 0
    stage = gui.current_stage if gui else 1
    pk_seq = int(config.system_settings.get('pk_sequence_mode', 0))
    is_pk_seq = (mode == 1 and (pk_seq == 1 or pk_seq == 2))
    
    pk_scores = {}
    if is_pk_seq:
        try:
            pk_scores = calc_pk_history_scores()
        except Exception as e:
            print(f"Error calculating pk history scores: {e}")
    
    stop_payload = {
        'final_score': final_score,
        'rank': rank,
        'mode': mode,
        'stage': stage,
        'is_pk_seq': is_pk_seq,
        'pk_scores': pk_scores
    }
    # 將最終結果儲存到全域狀態，方便重連時還原畫面
    config.current_state['last_stop_data'] = stop_payload
    
    socketio.emit('scoring_stop', stop_payload)
