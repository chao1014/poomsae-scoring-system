const socket = io({
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    randomizationFactor: 0.5,
    timeout: 20000
});

// 全域事件監聽 (除錯用)
socket.onAny((event, ...args) => {
    console.log(`[SocketIO Received Event] "${event}":`, args);
});

// 監聽連線狀態
socket.on('connect', () => {
    console.log('Socket.IO connected');
    const statusText = document.getElementById('connection-status-text');
    if (statusText) {
        statusText.innerHTML = '<span class="pulse-dot" style="background-color: var(--color-success); box-shadow: 0 0 8px var(--color-success);"></span>已連線，等待賽事啟動...';
        statusText.style.color = 'var(--color-success)';
    }
    // Wi-Fi 瞬斷重連時自動發送 join_judge
    if (myJudgeId) {
        console.log('自動重連發送 join_judge:', myJudgeId);
        socket.emit('join_judge', { judge_id: myJudgeId });
    }
});

socket.on('disconnect', (reason) => {
    console.log('Socket.IO disconnected:', reason);
    const statusText = document.getElementById('connection-status-text');
    if (statusText) {
        statusText.innerHTML = '<span class="pulse-dot" style="background-color: var(--color-danger); box-shadow: 0 0 8px var(--color-danger);"></span>連線中斷，正在重新連線...';
        statusText.style.color = 'var(--color-danger)';
    }
    // 如果已經在評分畫面中，強制退回等待畫面
    if (document.getElementById('scoring-screen') && !document.getElementById('scoring-screen').classList.contains('hidden')) {
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('scoring-screen').classList.add('hidden');
        document.getElementById('waiting-screen').classList.remove('hidden');
    }
    // 同步隱藏 PK 評分畫面
    const pkScreen = document.getElementById('pk-scoring-screen');
    if (pkScreen && !pkScreen.classList.contains('hidden')) {
        pkScreen.classList.add('hidden');
        document.getElementById('waiting-screen').classList.remove('hidden');
    }
});

socket.on('connect_error', (error) => {
    console.error('Socket.IO connection error:', error);
    const statusText = document.getElementById('connection-status-text');
    if (statusText) {
        statusText.innerHTML = '<span class="pulse-dot" style="background-color: var(--color-danger); box-shadow: 0 0 8px var(--color-danger);"></span>連線失敗，請檢查網路';
        statusText.style.color = 'var(--color-danger)';
    }
});

// 監聽後端傳來的狀態更新 (包含賽事與場地資訊)
socket.on('status_update', (data) => {
    if (data.tournament_name) {
        const tName = document.getElementById('waiting-tournament-name');
        if (tName) tName.innerText = data.tournament_name;
    }
    if (data.court_no) {
        const cNo = document.getElementById('waiting-court-no');
        if (cNo) cNo.innerText = `第 ${data.court_no} 場地`;
    }
});

socket.on('connected_judges_update', (data) => {
    const connected = data.connected || [];
    const buttons = document.querySelectorAll('.btn-judge-select');
    buttons.forEach(btn => {
        const judgeId = btn.innerText.trim();
        // 若該號碼已被連線且不是自己目前的身份，則設定為已連線狀態
        if (connected.includes(judgeId) && judgeId !== myJudgeId) {
            btn.classList.add('connected');
            btn.disabled = true;
        } else {
            btn.classList.remove('connected');
            btn.disabled = false;
        }
    });
});

let myJudgeId = "";
let currentMode = 0; // 0: Cutoff, 1: PK, 2: Freestyle, 3: Quick
let currentStage = 1;
let currentPkSequenceMode = 0;
let currentPlayerSide = 0;
let hasSecondRound = false;
let countdownInterval = null;
let currentCountdownSec = 90;
let screenBeforeLeaderboard = null;

// 評分狀態變數 (公認品勢)
let cntMinor = 0; // 小錯 -0.1 次數
let cntMajor = 0; // 大錯 -0.3 次數
let poomsaeSubScores = {
    p1: 2.0, // 速度與力量
    p2: 2.0, // 節奏與協調
    p3: 2.0  // 精神表現
};
let presentationSingle = 6.0; // 一般/非細分表現性分數

// 評分狀態變數 (自由品勢 10 項)
// 技術分 6 項 (滿分各 1.0)
const freestyleTechKeys = [
    { id: 't1', label: '跳躍高度' },
    { id: 't2', label: '空中踢腿次數' },
    { id: 't3', label: '旋風踢旋轉角度' },
    { id: 't4', label: '連續踢擊表現' },
    { id: 't5', label: '特技動作' },
    { id: 't6', label: '基本動作與實用性' }
];
// 表現分 4 項 (滿分各 1.0)
const freestylePresKeys = [
    { id: 'pr1', label: '創意' },
    { id: 'pr2', label: '和諧性' },
    { id: 'pr3', label: '氣勢' },
    { id: 'pr4', label: '音樂與編舞' }
];
let freestyleScores = {};

// Screen Wake Lock
let wakeLock = null;

// ==========================================
// 1. 登入連線邏輯
// ==========================================

// 展開/收摺自訂登入
function toggleCustomLogin() {
    const box = document.getElementById('custom-login-box');
    box.classList.toggle('hidden');
    triggerVibrate(20);
}

// 請求進入全螢幕模式 (需由使用者互動事件觸發)
function enterFullscreen() {
    const docEl = document.documentElement;
    try {
        if (docEl.requestFullscreen) {
            const promise = docEl.requestFullscreen();
            if (promise !== undefined) {
                promise.catch(err => console.log(`[Info] 全螢幕請求被忽略 (需使用者互動或設備不支援): ${err.message}`));
            }
        } else if (docEl.webkitRequestFullscreen) { /* Safari, Chrome, Opera */
            docEl.webkitRequestFullscreen();
        } else if (docEl.mozRequestFullScreen) { /* Firefox */
            docEl.mozRequestFullScreen();
        } else if (docEl.msRequestFullscreen) { /* IE/Edge */
            docEl.msRequestFullscreen();
        }
    } catch (err) {
        console.log('[Info] 全螢幕 API 啟動失敗 (可能受限於瀏覽器或設備):', err.message);
    }
}

// 切換全螢幕狀態
function toggleFullscreen() {
    const docEl = document.documentElement;
    const isFullscreen = document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    if (!isFullscreen) {
        enterFullscreen();
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) { /* Safari */
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) { /* Firefox */
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) { /* IE/Edge */
            document.msExitFullscreen();
        }
    }
}

// 強制鎖定橫屏 (需由使用者互動事件觸發)
function lockLandscape() {
    if (screen.orientation && typeof screen.orientation.lock === 'function') {
        screen.orientation.lock('landscape').then(() => {
            console.log('螢幕方向已鎖定為橫屏 (Landscape)');
        }).catch((err) => {
            // AbortError 或是 NotSupportedError 在許多設備(如電腦/iOS)上是預期的，不視為錯誤
            console.log(`[Info] 設備不支援強制鎖定橫向 (${err.name})，將以 CSS 直屏遮罩引導用戶`);
        });
    }
}

// 點選快速代號
function selectJudge(judgeId) {
    document.getElementById('judge-id').value = judgeId;
    triggerVibrate(30);
    enterFullscreen();
    lockLandscape();
    enableNoSleep();
    joinSystem(true);
}

// 加入連線系統
function joinSystem(alreadyInitiated = false) {
    const inputId = document.getElementById('judge-id').value.trim();
    if (!inputId) {
        alert("請輸入或點選代號");
        return;
    }
    myJudgeId = inputId;
    
    // 將裁判代號寫入 sessionStorage，以便重新整理時能自動登入
    sessionStorage.setItem('poomsae_judge_id', myJudgeId);
    
    // 建立防休眠影片 (不管是否為自動登入，都先建立，以便後續點擊時能直接播放)
    enableNoSleep();
    
    // 再次嘗試進入全螢幕與鎖定橫屏 (以防 selectJudge 沒被點擊)
    if (!alreadyInitiated) {
        enterFullscreen();
        lockLandscape();
    }
    
    // 更新登入標記
    document.getElementById('display-judge-id').innerText = myJudgeId;
    document.getElementById('display-judge-id-live').innerText = myJudgeId;
    const largeJudgeId = document.getElementById('waiting-display-judge-id-large');
    if (largeJudgeId) largeJudgeId.innerText = myJudgeId;

    
    // 先切換畫面至等待頁面，避免 Socket 響應過快導致 UI 狀態競爭 (Race Condition)
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('scoring-screen').classList.add('hidden');
    
    const pkScoringScreen = document.getElementById('pk-scoring-screen');
    if (pkScoringScreen) pkScoringScreen.classList.add('hidden');
    const pkSubmittedOverlay = document.getElementById('pk-submitted-overlay');
    if (pkSubmittedOverlay) pkSubmittedOverlay.classList.add('hidden');
    const rankingScreen = document.getElementById('ranking-screen');
    if (rankingScreen) rankingScreen.classList.add('hidden');
    
    document.getElementById('waiting-screen').classList.remove('hidden');
    
    // 再發送加入事件
    socket.emit('join_judge', { judge_id: myJudgeId });
    
    // 請求螢幕常亮
    requestWakeLock();
    triggerVibrate([40, 40, 40]);
}

// 手動切換裁判代號並返回登入畫面
function changeJudge() {
    socket.emit('leave_judge');
    sessionStorage.removeItem('poomsae_judge_id');
    myJudgeId = "";
    document.getElementById('waiting-screen').classList.add('hidden');
    document.getElementById('scoring-screen').classList.add('hidden');
    
    const pkScoringScreen = document.getElementById('pk-scoring-screen');
    if (pkScoringScreen) pkScoringScreen.classList.add('hidden');
    const pkSubmittedOverlay = document.getElementById('pk-submitted-overlay');
    if (pkSubmittedOverlay) pkSubmittedOverlay.classList.add('hidden');
    const rankingScreen = document.getElementById('ranking-screen');
    if (rankingScreen) rankingScreen.classList.add('hidden');
    
    // 清除 PK 主題
    const ss = document.getElementById('scoring-screen');
    if (ss) ss.classList.remove('pk-chung-theme', 'pk-hong-theme');
    const rt = document.getElementById('pk-single-role-tag');
    if (rt) rt.classList.add('hidden');
    
    document.getElementById('login-screen').classList.remove('hidden');
    triggerVibrate(30);
}

// ==========================================
// 輔助函式：型場中英文輪替顯示
// ==========================================
function formatPoomsaeText(rawText) {
    if (!rawText || typeof rawText !== 'string') return rawText || "---";
    
    // 尋找第一個空白字元作為中英文的切割點 (格式例如："太極一章 Taegeuk1")
    const firstSpaceIndex = rawText.indexOf(' ');
    
    if (firstSpaceIndex !== -1) {
        const zh = rawText.substring(0, firstSpaceIndex).trim();
        const en = rawText.substring(firstSpaceIndex + 1).trim();
        
        if (zh && en) {
            return `<span class="poomsae-anim-container"><span class="poomsae-anim-zh">${zh}</span><span class="poomsae-anim-en">${en}</span></span>`;
        }
    }
    return rawText;
}

// ==========================================
// 2. 監聽伺服器廣播事件
// ==========================================

// 開始評分廣播
socket.on('scoring_start', (data) => {
    if (!myJudgeId) return;
    try {
        // 解析伺服器發送的比賽資訊
        currentMode = data.mode !== undefined ? data.mode : 0;
        currentStage = data.stage !== undefined ? data.stage : 1;
        const pkSeqMode = data.pk_sequence_mode !== undefined ? data.pk_sequence_mode : 0;
        const playerSide = data.player_side !== undefined ? data.player_side : 0;
        currentPkSequenceMode = pkSeqMode;
        currentPlayerSide = playerSide;
        
        // 若為 PK 同時上場模式，轉向 PK 首層雙排介面
        if (currentMode === 1 && pkSeqMode === 0) {
            showPkScoringScreen(data);
            return;
        }
        
        // 清除上一次可能套用過的 PK 色彩主題
        const scoringScreen = document.getElementById('scoring-screen');
        scoringScreen.classList.remove('pk-chung-theme', 'pk-hong-theme');
        
        // PK 衣叁角落提示標簽
        const roleTag = document.getElementById('pk-single-role-tag');
        if (roleTag) {
            roleTag.classList.add('hidden');
            roleTag.innerText = '';
        }
        
        // 若為 PK 交叉/依序上場模式，套用對應的顏色主題與提示
        if (currentMode === 1 && pkSeqMode !== 0) {
            if (playerSide === 0) {
                scoringScreen.classList.add('pk-chung-theme');
                if (roleTag) {
                    roleTag.innerText = '🔵 青方 (Chung) 評分中';
                    roleTag.style.background = 'rgba(0, 80, 200, 0.85)';
                    roleTag.classList.remove('hidden');
                }
            } else {
                scoringScreen.classList.add('pk-hong-theme');
                if (roleTag) {
                    roleTag.innerText = '🔴 紅方 (Hong) 評分中';
                    roleTag.style.background = 'rgba(180, 0, 30, 0.85)';
                    roleTag.classList.remove('hidden');
                }
            }
            // 更新選手資訊塗山：顯示正在評分的選手姓名與單位
            const showChung = (playerSide === 0);
            const infoPlayer = document.getElementById('info-player');
            if (infoPlayer) infoPlayer.innerText = showChung
                ? (data.chung_player || data.player || '---')
                : (data.hong_player || '---');
            const infoTeam = document.getElementById('info-team');
            if (infoTeam) infoTeam.innerText = showChung
                ? (data.chung_team || data.team || '---')
                : (data.hong_team || '---');
        } else {
            // 更新選手資訊卡第一行
            const infoTeam = document.getElementById('info-team');
            if (infoTeam) infoTeam.innerText = data.team || "---";
            
            const infoPlayer = document.getElementById('info-player');
            if (infoPlayer) infoPlayer.innerText = data.player || "---";
        }
        
        const infoNo = document.getElementById('info-no');
        if (infoNo) infoNo.innerText = data.no || "---";
        
        const infoCategory = document.getElementById('info-category');
        if (infoCategory) infoCategory.innerText = data.category || "---";
        
        const infoDivision = document.getElementById('info-division');
        if (infoDivision) infoDivision.innerText = data.division || "---";
        
        const infoPhase = document.getElementById('info-phase');
        if (infoPhase) infoPhase.innerText = data.phase || "---";
        
        const infoType = document.getElementById('info-type');
        if (infoType) infoType.innerText = data.match_type || "---";
        
        // 更新第二行的型場名稱
        const infoPoomsaeR1 = document.getElementById('info-poomsae-r1');
        if (infoPoomsaeR1) infoPoomsaeR1.innerHTML = formatPoomsaeText(data.poomsae_1 || "---");
        
        const infoPoomsaeR2 = document.getElementById('info-poomsae-r2');
        const tagR1 = document.getElementById('poomsae-stage-r1');
        const tagR2 = document.getElementById('poomsae-stage-r2');
        
        // 動態判斷是否顯示 R2
        hasSecondRound = !!(data.poomsae_2 && !data.poomsae_2.includes("不需選擇") && data.poomsae_2.trim() !== "");
        if (hasSecondRound) {
            if (infoPoomsaeR2) infoPoomsaeR2.innerHTML = formatPoomsaeText(data.poomsae_2);
            if (tagR2) tagR2.classList.remove('hidden');
        } else {
            if (infoPoomsaeR2) infoPoomsaeR2.innerText = "";
            if (tagR2) tagR2.classList.add('hidden');
        }
        
        // 高亮當前評分的型場，並隱藏非當前回合
        if (tagR1 && tagR2) {
            tagR1.classList.remove('active-stage');
            tagR2.classList.remove('active-stage');
            if (currentStage === 2 && data.poomsae_2 && !data.poomsae_2.includes("不需選擇")) {
                tagR2.classList.add('active-stage');
                tagR1.classList.add('hidden'); // 進行 R2 時隱藏 R1
                tagR2.classList.remove('hidden');
            } else {
                tagR1.classList.add('active-stage');
                tagR1.classList.remove('hidden');
                tagR2.classList.add('hidden'); // 進行 R1 時隱藏 R2
            }
        }
        
        // 重置所有分數為初始値
        resetScoringData();
        
        // 啟用並恢復送出按鈕
        const btnSubmit = document.getElementById('btn-submit');
        btnSubmit.disabled = false;
        btnSubmit.innerText = "送出評分";
        
        if (currentMode === 2) {
            // 自由品勢模式
            scoringScreen.classList.remove('layout-classic');
            scoringScreen.classList.add('layout-freestyle');
            
            document.getElementById('accuracy-panel').classList.add('hidden');
            document.getElementById('presentation-panel').classList.add('hidden');
            document.getElementById('freestyle-panel').classList.remove('hidden');
            renderFreestylePanel();
        } else {
            // 公認品勢 / PK 模式 / 快速模式
            scoringScreen.classList.remove('layout-freestyle');
            scoringScreen.classList.add('layout-classic');
            
            document.getElementById('accuracy-panel').classList.remove('hidden');
            document.getElementById('presentation-panel').classList.remove('hidden');
            document.getElementById('freestyle-panel').classList.add('hidden');
            
            // 預設採用細細項 (p1, p2, p3) 評分
            document.getElementById('presentation-details').classList.remove('hidden');
            document.getElementById('presentation-single').classList.add('hidden');
        }
        
        updateTotals();
        
        // 重置等待覆蓋層的狀態，為下一位選手做準備
        const overlayTitle = document.querySelector('#submitted-overlay h2');
        if (overlayTitle) {
            overlayTitle.innerText = "評分已成功送出";
        }
        const overlayDesc = document.querySelector('#submitted-overlay p');
        if (overlayDesc) {
            overlayDesc.innerText = "等待統計分數...";
        }
        const overlayScoreBox = document.querySelector('.overlay-scores-container');
        if (overlayScoreBox) {
            overlayScoreBox.classList.remove('hidden');
        }
        const finalResultBox = document.getElementById('final-result-box');
        if (finalResultBox) {
            finalResultBox.classList.add('hidden');
        }
        const pkResultBox = document.getElementById('pk-result-box');
        if (pkResultBox) {
            pkResultBox.classList.add('hidden');
        }
        document.getElementById('submitted-overlay').classList.add('hidden');
        
        // 初始化計時器顯示為 1:30，但不啟動倒數（等待主控端 timer_sync 信號）
        stopCountdownTimer();
        const timerValEl = document.getElementById('val-timer');
        if (timerValEl) {
            timerValEl.innerText = "1:30";
            timerValEl.style.color = 'var(--color-warning)';
            timerValEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
        }
        
        // 切換畫面
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('waiting-screen').classList.add('hidden');
        document.getElementById('pk-scoring-screen').classList.add('hidden');
        const rankingScreen = document.getElementById('ranking-screen');
        if (rankingScreen) rankingScreen.classList.add('hidden');
        document.getElementById('scoring-screen').classList.remove('hidden');
        
        // 確保 WakeLock 仍然有效
        requestWakeLock();
        triggerVibrate(80);
    } catch (err) {
        alert("評分畫面切換發生 JS 錯誤: " + err.message + "\n" + err.stack);
    }
});

// 停止評分廣播 (大螢幕展示分數，正式鎖定評分)
function applyStopScoringUI(data) {
    if (!myJudgeId) return;
    // 隱藏「修改分數」按鈕，正式鎖定不給修改
    const btnModify = document.getElementById('btn-modify-score');
    if (btnModify) btnModify.classList.add('hidden');
    const pkBtnModify = document.getElementById('pk-btn-modify-score');
    if (pkBtnModify) pkBtnModify.classList.add('hidden');
    
    // 隱藏原本的自評分數區
    const overlayScoreBox = document.querySelector('.overlay-scores-container');
    if (overlayScoreBox) overlayScoreBox.classList.add('hidden');
    
    // 更改等待覆蓋層文字以提示裁判
    const overlayTitle = document.querySelector('#submitted-overlay h2');
    if (overlayTitle) overlayTitle.innerText = '最終評分結果';
    const overlayDesc = document.querySelector('#submitted-overlay p');
    if (overlayDesc) overlayDesc.innerText = '評分已截止，以下為最終統計';
    
    const isPkSeq = data && data.is_pk_seq;
    const stage = data ? data.stage : 1;
    
    if (isPkSeq) {
        // PK 交叉/依序上場模式
        const finalResultBox = document.getElementById('final-result-box');
        if (finalResultBox) finalResultBox.classList.add('hidden');
        const pkResultBox = document.getElementById('pk-result-box');
        if (pkResultBox) pkResultBox.classList.remove('hidden');
        
        const pkScores = data.pk_scores || {};
        const chungR1 = pkScores.chung_1r !== undefined ? pkScores.chung_1r : 0.0;
        const hongR1 = pkScores.hong_1r !== undefined ? pkScores.hong_1r : 0.0;
        const cR1El = document.getElementById('pk-res-chung-r1');
        const hR1El = document.getElementById('pk-res-hong-r1');
        if (cR1El) cR1El.innerText = chungR1.toFixed(3);
        if (hR1El) hR1El.innerText = hongR1.toFixed(3);
        
        const pkResR2Board = document.getElementById('pk-res-r2-board');
        if (stage === 2) {
            const chungR2 = pkScores.chung_2r !== undefined ? pkScores.chung_2r : 0.0;
            const hongR2 = pkScores.hong_2r !== undefined ? pkScores.hong_2r : 0.0;
            const chungFinal = pkScores.chung_final !== undefined ? pkScores.chung_final : 0.0;
            const hongFinal = pkScores.hong_final !== undefined ? pkScores.hong_final : 0.0;
            const cR2El = document.getElementById('pk-res-chung-r2');
            const hR2El = document.getElementById('pk-res-hong-r2');
            const cFinEl = document.getElementById('pk-res-chung-final');
            const hFinEl = document.getElementById('pk-res-hong-final');
            if (cR2El) cR2El.innerText = chungR2.toFixed(3);
            if (hR2El) hR2El.innerText = hongR2.toFixed(3);
            if (cFinEl) cFinEl.innerText = chungFinal.toFixed(3);
            if (hFinEl) hFinEl.innerText = hongFinal.toFixed(3);
            if (pkResR2Board) pkResR2Board.classList.remove('hidden');
        } else {
            if (pkResR2Board) pkResR2Board.classList.add('hidden');
        }
        
        const isMatchFinished = (stage === 2) || (stage === 1 && !hasSecondRound);
        const winnerRow = document.getElementById('pk-res-winner-row');
        if (isMatchFinished) {
            let finalChung = 0.0;
            let finalHong = 0.0;
            if (stage === 2) {
                finalChung = pkScores.chung_final !== undefined ? pkScores.chung_final : 0.0;
                finalHong = pkScores.hong_final !== undefined ? pkScores.hong_final : 0.0;
            } else {
                finalChung = chungR1;
                finalHong = hongR1;
            }
            const winEl = document.getElementById('pk-res-winner-text');
            if (winEl) {
                const roundedChung = Number(finalChung.toFixed(3));
                const roundedHong = Number(finalHong.toFixed(3));
                const chungP = Number(pkScores.chung_p || 0);
                const hongP = Number(pkScores.hong_p || 0);
                const chungTot = Number(pkScores.chung_tot || 0);
                const hongTot = Number(pkScores.hong_tot || 0);
                let winner = '';
                if (roundedChung !== roundedHong) winner = roundedChung > roundedHong ? 'chung' : 'hong';
                else if (chungP !== hongP) winner = chungP > hongP ? 'chung' : 'hong';
                else if (chungTot !== hongTot) winner = chungTot > hongTot ? 'chung' : 'hong';

                if (winner === 'chung') {
                    winEl.innerText = "🔵 青方 獲勝 (Chung WIN)";
                    winEl.style.color = "#00ccff";
                    winEl.style.textShadow = "0 0 10px rgba(0,204,255,0.4)";
                } else if (winner === 'hong') {
                    winEl.innerText = "🔴 紅方 獲勝 (Hong WIN)";
                    winEl.style.color = "#ff3366";
                    winEl.style.textShadow = "0 0 10px rgba(255,51,102,0.4)";
                } else {
                    winEl.innerText = "🤝 雙方平手 (DRAW)";
                    winEl.style.color = "#f1c40f";
                    winEl.style.textShadow = "0 0 10px rgba(241,196,15,0.4)";
                }
            }
            if (winnerRow) winnerRow.classList.remove('hidden');
        } else {
            if (winnerRow) winnerRow.classList.add('hidden');
        }
    } else {
        // 一般賽制，或 PK 同時上場模式
        const pkResultBox = document.getElementById('pk-result-box');
        if (pkResultBox) pkResultBox.classList.add('hidden');
        const finalResultBox = document.getElementById('final-result-box');
        if (finalResultBox) finalResultBox.classList.remove('hidden');
        
        const finalValScore = document.getElementById('final-val-score');
        if (finalValScore && data && data.final_score !== undefined) {
            finalValScore.innerText = parseFloat(data.final_score).toFixed(3);
        }
        
        // 依照輪次調整標題與排名區塊
        const finalResultTitle = document.getElementById('final-result-title');
        const finalRankBox = document.getElementById('final-rank-box');
        if (stage === 1 && hasSecondRound) {
            if (finalResultTitle) finalResultTitle.innerText = '1R 評分結果';
            if (finalRankBox) finalRankBox.classList.add('hidden');
        } else {
            if (finalResultTitle) finalResultTitle.innerText = '最終得分';
            if (finalRankBox) finalRankBox.classList.remove('hidden');
            const finalValRank = document.getElementById('final-val-rank');
            if (finalValRank && data && data.rank !== undefined) {
                finalValRank.innerText = data.rank;
            }
        }
    }
    
    triggerVibrate(60);
}

socket.on('scoring_stop', (data) => {
    applyStopScoringUI(data);
});

// 重連後本地還原最終結果畫面（由 reconnect_state 分支觸發）
socket.on('_restore_stop_ui', (data) => {
    applyStopScoringUI(data);
});

// 恢復評分廣播 (本輪重評)
socket.on('scoring_resume', () => {
    if (!myJudgeId) return;
    // 隱藏最終分數與排名區塊
    const finalResultBox = document.getElementById('final-result-box');
    if (finalResultBox) {
        finalResultBox.classList.add('hidden');
    }
    const pkResultBox = document.getElementById('pk-result-box');
    if (pkResultBox) {
        pkResultBox.classList.add('hidden');
    }
    const rankingScreen = document.getElementById('ranking-screen');
    if (rankingScreen) rankingScreen.classList.add('hidden');
    
    // 顯示「修改分數」按鈕
    const btnModify = document.getElementById('btn-modify-score');
    if (btnModify) {
        btnModify.classList.remove('hidden');
    }
    const pkBtnModify = document.getElementById('pk-btn-modify-score');
    if (pkBtnModify) {
        pkBtnModify.classList.remove('hidden');
    }
    
    // 顯示自評分數區
    const overlayScoreBox = document.querySelector('.overlay-scores-container');
    if (overlayScoreBox) {
        overlayScoreBox.classList.remove('hidden');
    }
    
    // 更改等待覆蓋層文字回到已送出狀態
    const overlayTitle = document.querySelector('#submitted-overlay h2');
    if (overlayTitle) {
        overlayTitle.innerText = "評分已成功送出";
    }
    const overlayDesc = document.querySelector('#submitted-overlay p');
    if (overlayDesc) {
        overlayDesc.innerText = "等待統計分數...";
    }
});

socket.on('reconnect_state', (data) => {
        if (data) {
            console.log('Received reconnect state:', data);
            currentMode = data.mode !== undefined ? data.mode : 0;
            currentStage = data.stage !== undefined ? data.stage : 1;
            const pkSeqMode = data.pk_sequence_mode !== undefined ? data.pk_sequence_mode : 0;
            const playerSide = data.current_player_side !== undefined ? data.current_player_side : 0;
            currentPkSequenceMode = pkSeqMode;
            currentPlayerSide = playerSide;
            const isPkSeq = (currentMode === 1 && pkSeqMode !== 0);
            
            // 1. 還原打分變數
            if (currentMode === 1 && pkSeqMode === 0) {
                // PK 同時上場模式
                let accChung = data.accuracy !== undefined ? data.accuracy : 4.0;
                pkScores.chung.cntMinor = Math.max(0, Math.round(parseFloat((4.0 - accChung).toFixed(1)) / 0.1));
                pkScores.chung.cntMajor = 0;
                pkScores.chung.p1 = data.p1 !== undefined ? data.p1 : 2.0;
                pkScores.chung.p2 = data.p2 !== undefined ? data.p2 : 2.0;
                pkScores.chung.p3 = data.p3 !== undefined ? data.p3 : 2.0;

                let accHong = data.hong_accuracy !== undefined ? data.hong_accuracy : 4.0;
                pkScores.hong.cntMinor = Math.max(0, Math.round(parseFloat((4.0 - accHong).toFixed(1)) / 0.1));
                pkScores.hong.cntMajor = 0;
                pkScores.hong.p1 = data.hong_p1 !== undefined ? data.hong_p1 : 2.0;
                pkScores.hong.p2 = data.hong_p2 !== undefined ? data.hong_p2 : 2.0;
                pkScores.hong.p3 = data.hong_p3 !== undefined ? data.hong_p3 : 2.0;

                // 同步更新 PK 的 UI
                pkUpdateAllUI();
            } else if (currentMode === 2) {
                // 自由品勢
                freestyleScores = data.freestyle_scores || {};
                freestyleTechKeys.forEach(k => {
                    if (freestyleScores[k.id] === undefined) freestyleScores[k.id] = 1.0;
                });
                freestylePresKeys.forEach(k => {
                    if (freestyleScores[k.id] === undefined) freestyleScores[k.id] = 1.0;
                });
            } else {
                // 一般公認品勢，或 PK 交叉/依序上場
                let accScore = 4.0;
                let p1 = 2.0, p2 = 2.0, p3 = 2.0;
                
                if (isPkSeq && playerSide === 1) {
                    accScore = data.hong_accuracy !== undefined ? data.hong_accuracy : 4.0;
                    p1 = data.hong_p1 !== undefined ? data.hong_p1 : 2.0;
                    p2 = data.hong_p2 !== undefined ? data.hong_p2 : 2.0;
                    p3 = data.hong_p3 !== undefined ? data.hong_p3 : 2.0;
                } else {
                    accScore = data.accuracy !== undefined ? data.accuracy : 4.0;
                    p1 = data.p1 !== undefined ? data.p1 : 2.0;
                    p2 = data.p2 !== undefined ? data.p2 : 2.0;
                    p3 = data.p3 !== undefined ? data.p3 : 2.0;
                }
                
                let deduct = parseFloat((4.0 - accScore).toFixed(1));
                if (deduct < 0) deduct = 0;
                cntMinor = Math.round(deduct / 0.1);
                cntMajor = 0;
                
                poomsaeSubScores.p1 = p1;
                poomsaeSubScores.p2 = p2;
                poomsaeSubScores.p3 = p3;
                
                // 同步更新一般賽制 UI
                document.getElementById('cnt-minor').innerText = cntMinor;
                document.getElementById('cnt-major').innerText = cntMajor;
                document.getElementById('val-p1').innerText = poomsaeSubScores.p1.toFixed(1);
                document.getElementById('val-p2').innerText = poomsaeSubScores.p2.toFixed(1);
                document.getElementById('val-p3').innerText = poomsaeSubScores.p3.toFixed(1);
                updateTotals();
            }
            
            // 2. 還原版面配置 (一般 vs 自由品勢 vs PK)
            const scoringScreen = document.getElementById('scoring-screen');
            const pkScoringScreen = document.getElementById('pk-scoring-screen');
            
            scoringScreen.classList.remove('pk-chung-theme', 'pk-hong-theme');
            const roleTag = document.getElementById('pk-single-role-tag');
            if (roleTag) {
                roleTag.classList.add('hidden');
                roleTag.innerText = '';
            }
            
            if (currentMode === 1 && pkSeqMode === 0) {
                // PK 同時上場模式
                scoringScreen.classList.add('hidden');
                pkScoringScreen.classList.remove('hidden');
            } else if (currentMode === 2) {
                // 自由品勢模式
                pkScoringScreen.classList.add('hidden');
                scoringScreen.classList.remove('hidden');
                scoringScreen.classList.remove('layout-classic');
                scoringScreen.classList.add('layout-freestyle');
                document.getElementById('accuracy-panel').classList.add('hidden');
                document.getElementById('presentation-panel').classList.add('hidden');
                document.getElementById('freestyle-panel').classList.remove('hidden');
                renderFreestylePanel();
            } else {
                // 一般公認品勢模式，或 PK 交叉/依序上場
                pkScoringScreen.classList.add('hidden');
                scoringScreen.classList.remove('hidden');
                scoringScreen.classList.remove('layout-freestyle');
                scoringScreen.classList.add('layout-classic');
                document.getElementById('accuracy-panel').classList.remove('hidden');
                document.getElementById('presentation-panel').classList.remove('hidden');
                document.getElementById('freestyle-panel').classList.add('hidden');
                document.getElementById('presentation-details').classList.remove('hidden');
                document.getElementById('presentation-single').classList.add('hidden');
                
                // 套用交叉/依序的主題與提示標簽
                if (isPkSeq) {
                    if (playerSide === 0) {
                        scoringScreen.classList.add('pk-chung-theme');
                        if (roleTag) {
                            roleTag.innerText = '🔵 青方 (Chung) 評分中';
                            roleTag.style.background = 'rgba(0, 80, 200, 0.85)';
                            roleTag.classList.remove('hidden');
                        }
                    } else {
                        scoringScreen.classList.add('pk-hong-theme');
                        if (roleTag) {
                            roleTag.innerText = '🔴 紅方 (Hong) 評分中';
                            roleTag.style.background = 'rgba(180, 0, 30, 0.85)';
                            roleTag.classList.remove('hidden');
                        }
                    }
                }
            }
            
            // 3. 還原頂部選手資訊卡 (使用 player_payload)
            if (data.player_payload) {
                const p = data.player_payload;
                if (currentMode === 1 && pkSeqMode === 0) {
                    // PK 同時上場的資訊還原
                    const infoType = document.getElementById('pk-info-type');
                    if (infoType) infoType.innerText = p.match_type || '---';
                    
                    const infoCategory = document.getElementById('pk-info-category');
                    if (infoCategory) infoCategory.innerText = p.category || '---';
                    
                    const infoDivision = document.getElementById('pk-info-division');
                    if (infoDivision) infoDivision.innerText = p.division || '---';
                    
                    const infoPhase = document.getElementById('pk-info-phase');
                    if (infoPhase) infoPhase.innerText = p.phase || '---';
                    
                    const displayJudge = document.getElementById('pk-display-judge-id-live');
                    if (displayJudge) displayJudge.innerText = myJudgeId;
                    
                    const chungTeam = document.getElementById('pk-chung-team');
                    if (chungTeam) chungTeam.innerText = p.chung_team || p.team || '---';
                    
                    const chungName = document.getElementById('pk-chung-name');
                    if (chungName) chungName.innerText = p.chung_player || p.player || '---';
                    
                    const hongTeam = document.getElementById('pk-hong-team');
                    if (hongTeam) hongTeam.innerText = p.hong_team || '---';
                    
                    const hongName = document.getElementById('pk-hong-name');
                    if (hongName) hongName.innerText = p.hong_player || '---';
                    
                    // 型場 R1/R2 標籤
                    const pkTagR1 = document.getElementById('pk-poomsae-stage-r1');
                    const pkTagR2 = document.getElementById('pk-poomsae-stage-r2');
                    const pkInfoR1 = document.getElementById('pk-info-poomsae-r1');
                    const pkInfoR2 = document.getElementById('pk-info-poomsae-r2');
                    if (pkInfoR1) pkInfoR1.innerHTML = formatPoomsaeText(p.poomsae_1 || '---');
                    if (p.poomsae_2 && !p.poomsae_2.includes('不需選擇')) {
                        if (pkInfoR2) pkInfoR2.innerHTML = formatPoomsaeText(p.poomsae_2);
                    } else {
                        if (pkInfoR2) pkInfoR2.innerText = '';
                    }
                    if (pkTagR1 && pkTagR2) {
                        pkTagR1.classList.remove('active-stage', 'hidden');
                        pkTagR2.classList.remove('active-stage', 'hidden');
                        if (currentStage === 2 && p.poomsae_2 && !p.poomsae_2.includes('不需選擇')) {
                            pkTagR1.classList.add('hidden');
                            pkTagR2.classList.add('active-stage');
                        } else {
                            pkTagR1.classList.add('active-stage');
                            pkTagR2.classList.add('hidden');
                        }
                    }
                } else {
                    // 一般賽制，或 PK 交叉/依序上場
                    const showChung = (!isPkSeq || playerSide === 0);
                    
                    const infoTeam = document.getElementById('info-team');
                    if (infoTeam) infoTeam.innerText = showChung
                        ? (p.chung_team || p.team || '---')
                        : (p.hong_team || '---');
                    
                    const infoPlayer = document.getElementById('info-player');
                    if (infoPlayer) infoPlayer.innerText = showChung
                        ? (p.chung_player || p.player || '---')
                        : (p.hong_player || '---');
                    
                    const infoNo = document.getElementById('info-no');
                    if (infoNo) infoNo.innerText = p.no || "---";
                    
                    const infoCategory = document.getElementById('info-category');
                    if (infoCategory) infoCategory.innerText = p.category || "---";
                    
                    const infoDivision = document.getElementById('info-division');
                    if (infoDivision) infoDivision.innerText = p.division || "---";
                    
                    const infoPhase = document.getElementById('info-phase');
                    if (infoPhase) infoPhase.innerText = p.phase || "---";
                    
                    const infoType = document.getElementById('info-type');
                    if (infoType) infoType.innerText = p.match_type || "---";
                    
                    const infoPoomsaeR1 = document.getElementById('info-poomsae-r1');
                    if (infoPoomsaeR1) infoPoomsaeR1.innerHTML = formatPoomsaeText(p.poomsae_1 || "---");
                    
                    const infoPoomsaeR2 = document.getElementById('info-poomsae-r2');
                    const tagR1 = document.getElementById('poomsae-stage-r1');
                    const tagR2 = document.getElementById('poomsae-stage-r2');
                    
                    hasSecondRound = !!(p.poomsae_2 && !p.poomsae_2.includes("不需選擇") && p.poomsae_2.trim() !== "");
                    if (hasSecondRound) {
                        if (infoPoomsaeR2) infoPoomsaeR2.innerHTML = formatPoomsaeText(p.poomsae_2);
                        if (tagR2) tagR2.classList.remove('hidden');
                    } else {
                        if (infoPoomsaeR2) infoPoomsaeR2.innerText = "";
                        if (tagR2) tagR2.classList.add('hidden');
                    }
                    
                    if (tagR1 && tagR2) {
                        tagR1.classList.remove('active-stage');
                        tagR2.classList.remove('active-stage');
                        if (currentStage === 2 && p.poomsae_2 && !p.poomsae_2.includes("不需選擇")) {
                            tagR2.classList.add('active-stage');
                            tagR1.classList.add('hidden');
                            tagR2.classList.remove('hidden');
                        } else {
                            tagR1.classList.add('active-stage');
                            tagR1.classList.remove('hidden');
                            tagR2.classList.add('hidden');
                        }
                    }
                }
            }
            
            // 4. 畫面整體狀態切換（登入、等待、評分中）及已送出覆蓋層還原
            if (data.is_scoring) {
                document.getElementById('login-screen').classList.add('hidden');
                document.getElementById('waiting-screen').classList.add('hidden');
                
                if (currentMode === 1 && pkSeqMode === 0) {
                    pkScoringScreen.classList.remove('hidden');
                    scoringScreen.classList.add('hidden');
                } else {
                    scoringScreen.classList.remove('hidden');
                    pkScoringScreen.classList.add('hidden');
                }
                
                let sideSubmitted = false;
                if (isPkSeq) {
                    sideSubmitted = (playerSide === 0) ? data.chung_submitted : data.hong_submitted;
                } else {
                    sideSubmitted = data.submitted;
                }
                
                if (sideSubmitted) {
                    stopCountdownTimer();
                    if (currentMode === 1 && pkSeqMode === 0) {
                        // 還原 PK 已送出覆蓋層
                        const chung = pkCalcSideScore('chung');
                        const hong  = pkCalcSideScore('hong');
                        
                        document.getElementById('pk-submitted-chung-total').innerText = chung.total.toFixed(1);
                        document.getElementById('pk-submitted-chung-acc').innerText = chung.acc.toFixed(1);
                        document.getElementById('pk-submitted-chung-pres').innerText = chung.pres.toFixed(1);
                        document.getElementById('pk-submitted-hong-total').innerText = hong.total.toFixed(1);
                        document.getElementById('pk-submitted-hong-acc').innerText = hong.acc.toFixed(1);
                        document.getElementById('pk-submitted-hong-pres').innerText = hong.pres.toFixed(1);
                        
                        document.getElementById('pk-submitted-overlay').classList.remove('hidden');
                    } else {
                        // 還原一般/自由品勢/PK交叉依序 已送出覆蓋層
                        let acc = 0;
                        let pres = 0;
                        let totalVal = 0.0;
                        
                        if (currentMode === 2) {
                            let techSum = 0;
                            let presSum = 0;
                            freestyleTechKeys.forEach(k => techSum += freestyleScores[k.id] || 0);
                            freestylePresKeys.forEach(k => presSum += freestyleScores[k.id] || 0);
                            acc = parseFloat(techSum.toFixed(1));
                            pres = parseFloat(presSum.toFixed(1));
                            totalVal = parseFloat((acc + pres).toFixed(1));
                        } else {
                            let tempAcc = 4.0;
                            let tempP1 = 2.0, tempP2 = 2.0, tempP3 = 2.0;
                            if (isPkSeq && playerSide === 1) {
                                tempAcc = data.hong_accuracy !== undefined ? data.hong_accuracy : 4.0;
                                tempP1 = data.hong_p1 !== undefined ? data.hong_p1 : 2.0;
                                tempP2 = data.hong_p2 !== undefined ? data.hong_p2 : 2.0;
                                tempP3 = data.hong_p3 !== undefined ? data.hong_p3 : 2.0;
                            } else {
                                tempAcc = data.accuracy !== undefined ? data.accuracy : 4.0;
                                tempP1 = data.p1 !== undefined ? data.p1 : 2.0;
                                tempP2 = data.p2 !== undefined ? data.p2 : 2.0;
                                tempP3 = data.p3 !== undefined ? data.p3 : 2.0;
                            }
                            
                            acc = tempAcc;
                            pres = tempP1 + tempP2 + tempP3;
                            totalVal = acc + pres;
                        }
                        
                        document.getElementById('submitted-val-total').innerText = totalVal.toFixed(1);
                        document.getElementById('submitted-val-acc').innerText = acc.toFixed(1);
                        document.getElementById('submitted-val-pres').innerText = pres.toFixed(1);
                        
                        document.getElementById('submitted-overlay').classList.remove('hidden');
                        document.getElementById('btn-modify-score').classList.remove('hidden');
                    }
                } else {
                    document.getElementById('submitted-overlay').classList.add('hidden');
                    document.getElementById('pk-submitted-overlay').classList.add('hidden');
                }
            } else {
                // 非評分狀態：判斷是否應還原最終結果畫面（scoring_stop 已觸發且裁判曾送出分數）
                const lastStop = data.last_stop_data;
                const wasStopped = !!lastStop && (data.submitted || data.chung_submitted || data.hong_submitted);

                if (wasStopped) {
                    // 還原最終結果畫面：切換到正確的評分畫面，並觸發一次 scoring_stop 的 UI 還原
                    document.getElementById('login-screen').classList.add('hidden');
                    document.getElementById('waiting-screen').classList.add('hidden');

                    if (currentMode === 1 && pkSeqMode === 0) {
                        pkScoringScreen.classList.remove('hidden');
                        scoringScreen.classList.add('hidden');
                        // 還原 PK 已送出覆蓋層
                        const chung = pkCalcSideScore('chung');
                        const hong  = pkCalcSideScore('hong');
                        document.getElementById('pk-submitted-chung-total').innerText = chung.total.toFixed(1);
                        document.getElementById('pk-submitted-chung-acc').innerText = chung.acc.toFixed(1);
                        document.getElementById('pk-submitted-chung-pres').innerText = chung.pres.toFixed(1);
                        document.getElementById('pk-submitted-hong-total').innerText = hong.total.toFixed(1);
                        document.getElementById('pk-submitted-hong-acc').innerText = hong.acc.toFixed(1);
                        document.getElementById('pk-submitted-hong-pres').innerText = hong.pres.toFixed(1);
                        document.getElementById('pk-submitted-overlay').classList.remove('hidden');
                    } else {
                        scoringScreen.classList.remove('hidden');
                        pkScoringScreen.classList.add('hidden');
                        // 還原已送出覆蓋層
                        document.getElementById('submitted-overlay').classList.remove('hidden');
                        document.getElementById('btn-modify-score').classList.add('hidden');
                    }

                    // 觸發 scoring_stop UI 還原：隱藏自評區、顯示最終結果
                    const overlayScoreBox = document.querySelector('.overlay-scores-container');
                    if (overlayScoreBox) overlayScoreBox.classList.add('hidden');
                    const overlayTitle = document.querySelector('#submitted-overlay h2');
                    if (overlayTitle) overlayTitle.innerText = '最終評分結果';
                    const overlayDesc = document.querySelector('#submitted-overlay p');
                    if (overlayDesc) overlayDesc.innerText = '評分已截止，以下為最終統計';

                    // 發送一個偽 scoring_stop 事件給本地的 UI 邏輯
                    applyStopScoringUI(lastStop);
                } else {
                    // 確實是等待中：顯示等待畫面
                    document.getElementById('login-screen').classList.add('hidden');
                    document.getElementById('scoring-screen').classList.add('hidden');
                    document.getElementById('pk-scoring-screen').classList.add('hidden');
                    document.getElementById('waiting-screen').classList.remove('hidden');
                }
            }

            // 5. 還原倒數時間與計時器顯示
            if (data.timer_seconds !== undefined) {
                currentCountdownSec = data.timer_seconds;
                
                // 同步一般計時器 DOM
                const timerValEl = document.getElementById('val-timer');
                if (timerValEl) {
                    timerValEl.innerText = formatTime(currentCountdownSec);
                    if (currentCountdownSec <= 10) {
                        timerValEl.style.color = 'var(--color-danger)';
                        timerValEl.style.textShadow = '0 0 12px rgba(255, 51, 102, 0.4)';
                    } else {
                        timerValEl.style.color = 'var(--color-warning)';
                        timerValEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
                    }
                }
                
                // 同步 PK 計時器 DOM
                const pkTimerEl = document.getElementById('pk-val-timer');
                if (pkTimerEl) {
                    pkTimerEl.innerText = formatTime(currentCountdownSec);
                    if (currentCountdownSec <= 10) {
                        pkTimerEl.style.color = 'var(--color-danger)';
                        pkTimerEl.style.textShadow = '0 0 12px rgba(255, 51, 102, 0.4)';
                    } else {
                        pkTimerEl.style.color = 'var(--color-warning)';
                        pkTimerEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
                    }
                }
            }
        }
    });

    // 重置賽事廣播
    socket.on('reset_match', () => {
        if (!myJudgeId) return;
        stopCountdownTimer();
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('scoring-screen').classList.add('hidden');
        document.getElementById('pk-scoring-screen').classList.add('hidden');
        const rankingScreen = document.getElementById('ranking-screen');
        if (rankingScreen) rankingScreen.classList.add('hidden');
        document.getElementById('waiting-screen').classList.remove('hidden');
    });

    // 監聽重複連線或超出裁判限制被拒絕事件
    socket.on('join_rejected', (data) => {
        if (data) {
            if (data.reason === 'already_connected') {
                alert(`該裁判代號 (${data.judge_id}) 目前已在其他設備連線中！\n若要更換設備，請聯絡主控台釋放連線。`);
            } else if (data.reason === 'judge_limit_exceeded') {
                alert(`此場地目前設定僅開放 ${data.max_judges} 位裁判！\n該編號 (${data.judge_id}) 已超出限制，請選擇正確的裁判代號。`);
            }
            // 清除快取並踢回登入畫面
            sessionStorage.removeItem('poomsae_judge_id');
            myJudgeId = "";
            document.getElementById('waiting-screen').classList.add('hidden');
            document.getElementById('login-screen').classList.remove('hidden');
            triggerVibrate(60);
        }
    });

    // 監聽強制斷線事件 (主控台釋放連線時觸發)
    socket.on('force_disconnect', () => {
        console.log('Force disconnected by host');
        sessionStorage.removeItem('poomsae_judge_id');
        myJudgeId = "";
        document.getElementById('waiting-screen').classList.add('hidden');
        document.getElementById('scoring-screen').classList.add('hidden');
        
        const pkScoringScreen = document.getElementById('pk-scoring-screen');
        if (pkScoringScreen) pkScoringScreen.classList.add('hidden');
        const pkSubmittedOverlay = document.getElementById('pk-submitted-overlay');
        if (pkSubmittedOverlay) pkSubmittedOverlay.classList.add('hidden');
        
        document.getElementById('login-screen').classList.remove('hidden');
        triggerVibrate([50, 100, 50]);
    });

// ==========================================
// 3. 評分核心計算與微調邏輯
// ==========================================

// 重置評分資料
function resetScoringData() {
    cntMinor = 0;
    cntMajor = 0;
    poomsaeSubScores.p1 = 2.0;
    poomsaeSubScores.p2 = 2.0;
    poomsaeSubScores.p3 = 2.0;
    presentationSingle = 6.0;
    
    // 重置自由品勢評分項目
    freestyleScores = {};
    freestyleTechKeys.forEach(k => freestyleScores[k.id] = 1.0);
    freestylePresKeys.forEach(k => freestyleScores[k.id] = 1.0);
    
    // 更新正確性統計畫面
    document.getElementById('cnt-minor').innerText = cntMinor;
    document.getElementById('cnt-major').innerText = cntMajor;
    
    // 更新細項畫面
    document.getElementById('val-p1').innerText = poomsaeSubScores.p1.toFixed(1);
    document.getElementById('val-p2').innerText = poomsaeSubScores.p2.toFixed(1);
    document.getElementById('val-p3').innerText = poomsaeSubScores.p3.toFixed(1);
}

// 點擊正確性扣分
function deductAccuracy(value) {
    if (value === 0.1) {
        cntMinor++;
        document.getElementById('cnt-minor').innerText = cntMinor;
        triggerVibrate(40); // 輕微震動
    } else if (value === 0.3) {
        cntMajor++;
        document.getElementById('cnt-major').innerText = cntMajor;
        triggerVibrate(90); // 顯著震動
    }
    updateTotals();
}

// 重設正確性扣分
function resetAccuracy() {
    cntMinor = 0;
    cntMajor = 0;
    document.getElementById('cnt-minor').innerText = cntMinor;
    document.getElementById('cnt-major').innerText = cntMajor;
    triggerVibrate(30);
    updateTotals();
}

// 顯示自訂確認退出連線 Modal
function confirmExit() {
    document.getElementById('confirm-modal').classList.remove('hidden');
    triggerVibrate(30);
}

// 關閉確認 Modal
function closeResetModal() {
    document.getElementById('confirm-modal').classList.add('hidden');
    triggerVibrate(20);
}

// 執行退出連線
function executeExit() {
    document.getElementById('confirm-modal').classList.add('hidden');
    // 清除快取並返回登入畫面 (changeJudge 內部會發送 leave_judge)
    changeJudge();
}

// 退回扣分 (加回分數與減少次數)
function undoDeduct(value) {
    if (value === 0.1) {
        if (cntMinor > 0) {
            cntMinor--;
            document.getElementById('cnt-minor').innerText = cntMinor;
            triggerVibrate(20); // 輕微回饋
        }
    } else if (value === 0.3) {
        if (cntMajor > 0) {
            cntMajor--;
            document.getElementById('cnt-major').innerText = cntMajor;
            triggerVibrate(20); // 輕微回饋
        }
    }
    updateTotals();
}

// 調整表現性三個細細項目 (p1, p2, p3)
function adjustPoomsaeSub(field, delta) {
    if (poomsaeSubScores[field] !== undefined) {
        let val = parseFloat((poomsaeSubScores[field] + delta).toFixed(1));
        if (val >= 0.0 && val <= 2.0) {
            poomsaeSubScores[field] = val;
            document.getElementById(`val-${field}`).innerText = val.toFixed(1);
            triggerVibrate(delta > 0 ? 30 : 20);
            updateTotals();
        }
    }
}

// 調整單一表現性評分 (備用非細分)
function adjustPresentationSingle(delta) {
    let val = parseFloat((presentationSingle + delta).toFixed(1));
    if (val >= 0.0 && val <= 6.0) {
        presentationSingle = val;
        document.getElementById('val-pres-single').innerText = val.toFixed(1);
        triggerVibrate(delta > 0 ? 30 : 20);
        updateTotals();
    }
}

// ==========================================
// 4. 自由品勢 (Freestyle) 動態介面與調整邏輯
// ==========================================

// 動態渲染自由品勢的 10 個調分欄位
function renderFreestylePanel() {
    const techBox = document.getElementById('freestyle-tech-items');
    const presBox = document.getElementById('freestyle-pres-items');
    
    techBox.innerHTML = "";
    presBox.innerHTML = "";
    
    // 渲染技術分 (6個)
    freestyleTechKeys.forEach(k => {
        techBox.appendChild(createFreestyleItemElement(k.id, k.label));
    });
    
    // 渲染表現分 (4個)
    freestylePresKeys.forEach(k => {
        presBox.appendChild(createFreestyleItemElement(k.id, k.label));
    });
}

// 建立自由品勢一個評分項目元件
function createFreestyleItemElement(id, label) {
    const item = document.createElement('div');
    item.className = 'pres-item';
    
    const title = document.createElement('span');
    title.className = 'pres-title';
    title.innerText = label;
    
    const rightWrapper = document.createElement('div');
    rightWrapper.className = 'pres-item-right-wrapper';
    
    const valDisplay = document.createElement('span');
    valDisplay.className = 'pres-val-display';
    valDisplay.id = `val-free-${id}`;
    valDisplay.innerText = (freestyleScores[id] || 1.0).toFixed(1);
    
    const controls = document.createElement('div');
    controls.className = 'pres-control-group';
    
    const btnMinus = document.createElement('button');
    btnMinus.className = 'btn-adjust';
    btnMinus.innerText = '-';
    btnMinus.onclick = () => adjustFreestyleSub(id, -0.1);
    
    const btnPlus = document.createElement('button');
    btnPlus.className = 'btn-adjust btn-plus';
    btnPlus.innerText = '+';
    btnPlus.onclick = () => adjustFreestyleSub(id, 0.1);
    
    controls.appendChild(btnMinus);
    controls.appendChild(btnPlus);
    
    rightWrapper.appendChild(valDisplay);
    rightWrapper.appendChild(controls);
    
    item.appendChild(title);
    item.appendChild(rightWrapper);
    
    return item;
}

// 調整自由品勢個別項目得分
function adjustFreestyleSub(id, delta) {
    if (freestyleScores[id] !== undefined) {
        let val = parseFloat((freestyleScores[id] + delta).toFixed(1));
        if (val >= 0.0 && val <= 1.0) {
            freestyleScores[id] = val;
            document.getElementById(`val-free-${id}`).innerText = val.toFixed(1);
            triggerVibrate(delta > 0 ? 30 : 20);
            updateTotals();
        }
    }
}

// ==========================================
// 5. 總分彙整與送出分數
// ==========================================

function syncScoreDraft() {
    if (!myJudgeId || !socket.connected) return;

    if (currentMode === 1 && currentPkSequenceMode === 0) {
        const chung = pkCalcSideScore('chung');
        const hong = pkCalcSideScore('hong');
        socket.emit('score_draft', {
            chung: { accuracy: chung.acc, presentation: chung.pres, p1: chung.p1, p2: chung.p2, p3: chung.p3 },
            hong: { accuracy: hong.acc, presentation: hong.pres, p1: hong.p1, p2: hong.p2, p3: hong.p3 }
        });
        return;
    }

    if (currentMode === 2) {
        let techSum = 0;
        let presSum = 0;
        freestyleTechKeys.forEach(k => techSum += freestyleScores[k.id] || 0);
        freestylePresKeys.forEach(k => presSum += freestyleScores[k.id] || 0);
        socket.emit('score_draft', {
            accuracy: parseFloat(techSum.toFixed(1)),
            presentation: parseFloat(presSum.toFixed(1)),
            p1: freestyleScores.t1 || 0,
            p2: freestyleScores.t2 || 0,
            p3: freestyleScores.t3 || 0,
            freestyle_scores: { ...freestyleScores }
        });
        return;
    }

    let acc = 4.0 - (cntMinor * 0.1) - (cntMajor * 0.3);
    if (acc < 0.0) acc = 0.0;
    const pres = poomsaeSubScores.p1 + poomsaeSubScores.p2 + poomsaeSubScores.p3;
    socket.emit('score_draft', {
        accuracy: parseFloat(acc.toFixed(1)),
        presentation: parseFloat(pres.toFixed(1)),
        p1: poomsaeSubScores.p1,
        p2: poomsaeSubScores.p2,
        p3: poomsaeSubScores.p3
    });
}

// 計算並更新總得分顯示，同步保存尚未送出的草稿
function updateTotals() {
    if (currentMode === 2) {
        // 自由品勢計算
        let techSum = 0;
        let presSum = 0;
        
        freestyleTechKeys.forEach(k => techSum += freestyleScores[k.id] || 0);
        freestylePresKeys.forEach(k => presSum += freestyleScores[k.id] || 0);
        
        const total = techSum + presSum;
        
        document.getElementById('val-free-total').innerText = total.toFixed(1);
        document.getElementById('val-total').innerText = total.toFixed(1);
    } else {
        // 公認品勢計算
        let acc = 4.0 - (cntMinor * 0.1) - (cntMajor * 0.3);
        if (acc < 0.0) acc = 0.0;
        
        // 採用細細項相加
        let pres = poomsaeSubScores.p1 + poomsaeSubScores.p2 + poomsaeSubScores.p3;
        
        const total = acc + pres;
        
        document.getElementById('val-acc').innerText = acc.toFixed(1);
        document.getElementById('val-pres').innerText = pres.toFixed(1);
        document.getElementById('val-total').innerText = total.toFixed(1);
    }
    syncScoreDraft();
}

// 送出評分結果
function submitScore() {
    let acc = 0;
    let pres = 0;
    let p1 = 0;
    let p2 = 0;
    let p3 = 0;
    
    if (currentMode === 2) {
        // 自由品勢
        let techSum = 0;
        let presSum = 0;
        freestyleTechKeys.forEach(k => techSum += freestyleScores[k.id] || 0);
        freestylePresKeys.forEach(k => presSum += freestyleScores[k.id] || 0);
        
        acc = parseFloat(techSum.toFixed(1));
        pres = parseFloat(presSum.toFixed(1));
        
        // 技術分前三個細項 mapping 欄位
        p1 = freestyleScores['t1'] || 0;
        p2 = freestyleScores['t2'] || 0;
        p3 = freestyleScores['t3'] || 0;
    } else {
        // 公認品勢
        acc = 4.0 - (cntMinor * 0.1) - (cntMajor * 0.3);
        if (acc < 0) acc = 0;
        acc = parseFloat(acc.toFixed(1));
        
        pres = poomsaeSubScores.p1 + poomsaeSubScores.p2 + poomsaeSubScores.p3;
        pres = parseFloat(pres.toFixed(1));
        
        p1 = poomsaeSubScores.p1;
        p2 = poomsaeSubScores.p2;
        p3 = poomsaeSubScores.p3;
    }
    
    // 透過 Socket 發送成績
    socket.emit('submit_score', {
        accuracy: acc,
        presentation: pres,
        p1: p1,
        p2: p2,
        p3: p3,
        freestyle_scores: currentMode === 2 ? { ...freestyleScores } : {}
    });
    
    // 停止倒數計時器
    stopCountdownTimer();
    
    // 顯示等待覆蓋層，並更新送出分數顯示
    const totalScore = parseFloat(document.getElementById('val-total').innerText);
    document.getElementById('submitted-val-total').innerText = totalScore.toFixed(1);
    document.getElementById('submitted-val-acc').innerText = acc.toFixed(1);
    document.getElementById('submitted-val-pres').innerText = pres.toFixed(1);
    document.getElementById('submitted-overlay').classList.remove('hidden');
    
    // 確保「修改分數」按鈕正常顯示
    document.getElementById('btn-modify-score').classList.remove('hidden');
    
    triggerVibrate([50, 100, 50]);
}

// 修改已送出的分數，返回重評介面
function modifySubmittedScore() {
    // 隱藏覆蓋層，裁判即可直接修改原本的評分並再次點擊送出
    document.getElementById('submitted-overlay').classList.add('hidden');
    
    // 通知後端清除電腦端（大螢幕與主控台）原先送出的分數
    socket.emit('modify_score');
    
    triggerVibrate(30);
}

// ==========================================
// 6. 行動硬體整合 API (常亮與震動)
// ==========================================

// 觸發硬體震動回饋 (安全封裝)
function triggerVibrate(pattern) {
    if ('vibrate' in navigator) {
        try {
            // 避免因自動登入而未經使用者互動前觸發震動，產生 Chrome Intervention 警告
            if (navigator.userActivation && !navigator.userActivation.hasBeenActive) {
                return;
            }
            navigator.vibrate(pattern);
        } catch(e) {}
    }
}

// 請求螢幕 Wake Lock (防止評分途中手機休眠)
async function requestWakeLock() {
    try {
        if ('wakeLock' in navigator) {
            // 若已有鎖且未被釋放，不重複請求
            if (wakeLock !== null) return;
            wakeLock = await navigator.wakeLock.request('screen');
            console.log('[WakeLock] 鎖定成功，螢幕將保持常亮');
            
            // 監聽釋放事件：清除鎖定狀態（點擊時會自動重新取得）
            wakeLock.addEventListener('release', () => {
                console.warn('[WakeLock] 已被系統釋放');
                wakeLock = null;
            });
        } else {
            console.warn('[WakeLock] 此平台不支援 Wake Lock API，依賴影片方案防休眠');
        }
    } catch (err) {
        console.warn(`[WakeLock] 請求失敗: ${err.name} - ${err.message}`);
        wakeLock = null;
    }
}

// 當頁面可見度改變 (例如手機切換 App 後再回評分網頁) 時，重新請求 Wake Lock 與恢復防休眠
document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'visible') {
        const isUserLoggedIn = document.getElementById('login-screen').classList.contains('hidden');
        if (isUserLoggedIn && wakeLock === null) {
            requestWakeLock();
        }
        // 恢復 AudioContext（切換 App 後可能被系統暫停）
        if (noSleepAudioCtx && noSleepAudioCtx.state === 'suspended') {
            noSleepAudioCtx.resume().catch(() => {});
        }
        if (noSleepVideo !== null) {
            noSleepVideo.play().catch(() => {});
        }
    }
});

// 防禦性設計：任何點擊互動都會嘗試取得/重取 WakeLock 並喚醒防休眠影片
document.addEventListener('click', () => {
    const isUserLoggedIn = document.getElementById('login-screen').classList.contains('hidden');
    if (isUserLoggedIn) {
        // 每次點擊都嘗試取得（函數內部會判斷是否已有鎖，避免重複）
        requestWakeLock();
        // 同步喚醒防休眠影片
        if (noSleepVideo === null) {
            enableNoSleep();
        } else {
            noSleepVideo.play().catch(() => {});
        }
    }
});

let noSleepVideo = null;
let noSleepAudioCtx = null;
let noSleepGainNode = null;
let noSleepOscillator = null;

// 主要防休眠方案：透過 AudioContext 建立無聲音訊會話
// iOS/Android 上只要音訊引擎持續活躍，系統就不會讓螢幕自動休眠
function enableNoSleep() {
    // ── 方案 A：AudioContext 無聲音訊會話 (最有效) ──
    if (!noSleepAudioCtx) {
        try {
            const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
            if (AudioCtxClass) {
                noSleepAudioCtx = new AudioCtxClass();
                noSleepGainNode = noSleepAudioCtx.createGain();
                noSleepGainNode.gain.value = 0.001; // 幾乎完全靜音，但音訊引擎保持活躍
                
                // 建立一個極低頻的震盪器（音訊人耳無法察覺，但引擎持續運作）
                noSleepOscillator = noSleepAudioCtx.createOscillator();
                noSleepOscillator.type = 'sine';
                noSleepOscillator.frequency.value = 1; // 1Hz，完全聽不到
                noSleepOscillator.connect(noSleepGainNode);
                noSleepGainNode.connect(noSleepAudioCtx.destination);
                noSleepOscillator.start();
                
                console.log('[NoSleep] AudioContext 無聲音訊會話已啟動，防止螢幕休眠');
            }
        } catch (e) {
            console.warn('[NoSleep] AudioContext 啟動失敗:', e.message);
        }
    } else if (noSleepAudioCtx.state === 'suspended') {
        // AudioContext 被瀏覽器暫停時（如切換 App），嘗試恢復
        noSleepAudioCtx.resume().catch(() => {});
    }

    // ── 方案 B：低音量影片備援 (非 iOS 裝置的第二層保障) ──
    // iOS Safari 對非使用者主動觸發的影片播放有嚴格限制，容易彈出系統提示，
    // 因此在 iOS 上只依賴方案 A（AudioContext）即可，跳過影片方案。
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (!isIOS && !noSleepVideo) {
        try {
            noSleepVideo = document.createElement('video');
            noSleepVideo.setAttribute('loop', '');
            noSleepVideo.setAttribute('playsinline', '');
            noSleepVideo.setAttribute('webkit-playsinline', '');
            // ★ 不設定 muted！改在 play 成功後設 volume 為幾乎無聲
            noSleepVideo.controls = false;
            // 保持在可見 viewport 內（4x4px），讓系統不暫停
            noSleepVideo.style.cssText = 'position:fixed;bottom:0;right:0;width:4px;height:4px;opacity:0.02;z-index:99999;pointer-events:none;';
            noSleepVideo.src = '/static/nosleep.mp4';
            document.body.appendChild(noSleepVideo);
            noSleepVideo.play().then(() => {
                // 播放成功後再把音量調到幾乎無聲（人耳完全無法察覺）
                noSleepVideo.volume = 0.001;
                console.log('[NoSleep] 非靜音影片播放中 (volume=0.001)，音訊路由已建立');
            }).catch((e) => {
                console.warn('[NoSleep] 影片播放失敗:', e.message);
            });
        } catch (err) {
            console.warn('[NoSleep] 無法建立影片:', err.message);
        }
    } else if (isIOS) {
        console.log('[NoSleep] iOS 裝置偵測到，跳過影片方案，依賴 AudioContext 防休眠。');
    }
}

// ==========================================
// 7. 快速評分邏輯 (Quick Scoring Logic)
// ==========================================

// 初始化快速評分按鈕
function initQuickScoring() {
    // 1. 正確性快速評分按鈕 (0.0 ~ 4.0)
    const accGrid = document.getElementById('quick-acc-grid');
    if (accGrid) {
        accGrid.innerHTML = "";
        // 0 到 40，換算為 0.0 到 4.0，避免 JavaScript 浮點數精度問題漏掉最後的 4.0
        for (let i = 0; i <= 40; i++) {
            let scoreVal = parseFloat((i / 10).toFixed(1));
            const btn = document.createElement('button');
            btn.className = 'btn-quick-num';
            btn.innerText = scoreVal.toFixed(1);
            if (scoreVal === 4.0) {
                btn.classList.add('span-all');
            }
            btn.dataset.score = scoreVal;
            btn.onclick = () => selectQuickAcc(scoreVal);
            accGrid.appendChild(btn);
        }
    }

    // 2. 表現性三細項快速評分按鈕 (0.0 ~ 2.0)
    const fields = ['p1', 'p2', 'p3'];
    fields.forEach(field => {
        const grid = document.getElementById(`quick-${field}-grid`);
        if (grid) {
            grid.innerHTML = "";
            // 0 到 20，換算為 0.0 到 2.0，避免 JavaScript 浮點數精度問題漏掉最後的 2.0
            for (let i = 0; i <= 20; i++) {
                let scoreVal = parseFloat((i / 10).toFixed(1));
                const btn = document.createElement('button');
                btn.className = 'btn-quick-num';
                btn.innerText = scoreVal.toFixed(1);
                btn.dataset.score = scoreVal;
                btn.onclick = () => selectQuickPres(field, scoreVal);
                grid.appendChild(btn);
            }
        }
    });
}

// 快速評分暫存變數
let tempAccScore = 4.0;
let tempPoomsaeSubScores = { p1: 2.0, p2: 2.0, p3: 2.0 };

// 開啟正確性快速評分
function openQuickAccModal() {
    const modal = document.getElementById('quick-acc-modal');
    if (modal) {
        // 讀取目前正確性得分，存入暫存
        let currentAcc = 4.0 - (cntMinor * 0.1) - (cntMajor * 0.3);
        if (currentAcc < 0) currentAcc = 0;
        tempAccScore = parseFloat(currentAcc.toFixed(1));

        // 刷新按鈕高亮狀態
        highlightAccTempButton();

        modal.classList.remove('hidden');
        triggerVibrate(30);
    }
}

// 選擇正確性快速評分分數 (僅修改暫存與更新彈窗內高亮)
function selectQuickAcc(score) {
    tempAccScore = score;
    highlightAccTempButton();
    triggerVibrate(30);
}

// 高亮正確性彈窗內對應暫存分數的按鈕
function highlightAccTempButton() {
    const modal = document.getElementById('quick-acc-modal');
    if (modal) {
        const buttons = modal.querySelectorAll('.btn-quick-num');
        buttons.forEach(btn => {
            const btnScore = parseFloat(btn.dataset.score);
            if (btnScore === tempAccScore) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
    }
}

// 確定正確性快速評分 (正式寫入並更新主頁面)
function confirmQuickAcc() {
    let deduct = parseFloat((4.0 - tempAccScore).toFixed(1));
    if (deduct < 0) deduct = 0;

    // 將所有扣分折算為 cntMinor，cntMajor 清零
    cntMinor = Math.round(deduct / 0.1);
    cntMajor = 0;

    // 更新扣分統計畫面
    document.getElementById('cnt-minor').innerText = cntMinor;
    document.getElementById('cnt-major').innerText = cntMajor;

    // 更新總分
    updateTotals();

    // 關閉彈窗
    document.getElementById('quick-acc-modal').classList.add('hidden');

    triggerVibrate(50);
}

// 取消正確性快速評分
function cancelQuickAcc() {
    document.getElementById('quick-acc-modal').classList.add('hidden');
    triggerVibrate(20);
}

// 開啟表現性快速評分
function openQuickPresModal() {
    const modal = document.getElementById('quick-pres-modal');
    if (modal) {
        // 複製目前分數到暫存
        tempPoomsaeSubScores.p1 = poomsaeSubScores.p1;
        tempPoomsaeSubScores.p2 = poomsaeSubScores.p2;
        tempPoomsaeSubScores.p3 = poomsaeSubScores.p3;

        // 更新標題旁的暫存數值顯示
        document.getElementById('quick-p1-current').innerText = tempPoomsaeSubScores.p1.toFixed(1);
        document.getElementById('quick-p2-current').innerText = tempPoomsaeSubScores.p2.toFixed(1);
        document.getElementById('quick-p3-current').innerText = tempPoomsaeSubScores.p3.toFixed(1);

        // 刷新按鈕高亮
        highlightPresTempButtons();

        modal.classList.remove('hidden');
        triggerVibrate(30);
    }
}

// 選擇表現性快速評分分數 (僅修改暫存與更新彈窗內顯示/高亮)
function selectQuickPres(field, score) {
    if (tempPoomsaeSubScores[field] !== undefined) {
        tempPoomsaeSubScores[field] = score;
        
        // 更新彈窗內的「目前: 數字」顯示
        document.getElementById(`quick-${field}-current`).innerText = score.toFixed(1);

        // 更新彈窗內的按鈕高亮狀態
        const grid = document.getElementById(`quick-${field}-grid`);
        if (grid) {
            const buttons = grid.querySelectorAll('.btn-quick-num');
            buttons.forEach(btn => {
                const btnScore = parseFloat(btn.dataset.score);
                if (btnScore === score) {
                    btn.classList.add('selected');
                } else {
                    btn.classList.remove('selected');
                }
            });
        }
        
        triggerVibrate(30);
    }
}

// 刷新表現性彈窗內按鈕高亮
function highlightPresTempButtons() {
    const fields = ['p1', 'p2', 'p3'];
    fields.forEach(field => {
        const curVal = tempPoomsaeSubScores[field];
        const grid = document.getElementById(`quick-${field}-grid`);
        if (grid) {
            const buttons = grid.querySelectorAll('.btn-quick-num');
            buttons.forEach(btn => {
                const btnScore = parseFloat(btn.dataset.score);
                if (btnScore === curVal) {

                    btn.classList.add('selected');
                } else {
                    btn.classList.remove('selected');
                }
            });
        }
    });
}

// 確定表現性快速評分 (正式寫入並更新主頁面)
function confirmQuickPres() {
    poomsaeSubScores.p1 = tempPoomsaeSubScores.p1;
    poomsaeSubScores.p2 = tempPoomsaeSubScores.p2;
    poomsaeSubScores.p3 = tempPoomsaeSubScores.p3;

    // 更新網頁上的細項數值顯示
    document.getElementById('val-p1').innerText = poomsaeSubScores.p1.toFixed(1);
    document.getElementById('val-p2').innerText = poomsaeSubScores.p2.toFixed(1);
    document.getElementById('val-p3').innerText = poomsaeSubScores.p3.toFixed(1);

    // 更新總分
    updateTotals();

    // 關閉彈窗
    document.getElementById('quick-pres-modal').classList.add('hidden');

    triggerVibrate(50);
}

// 取消表現性快速評分
function cancelQuickPres() {
    document.getElementById('quick-pres-modal').classList.add('hidden');
    triggerVibrate(20);
}

// 初始化執行
initQuickScoring();

// 網頁初始化載入時，檢查是否有 sessionStorage 快取，若有則自動登入
window.addEventListener('load', () => {
    const savedJudgeId = sessionStorage.getItem('poomsae_judge_id');
    if (savedJudgeId) {
        const inputEl = document.getElementById('judge-id');
        if (inputEl) {
            inputEl.value = savedJudgeId;
            console.log('偵測到快取的裁判代號，執行自動登入:', savedJudgeId);
            joinSystem(true);
        }
    }
});

// 大螢幕投影片切換監聽 (同步排行榜)
// Keep the exact visible state while the leaderboard is displayed.
function applyProjectionSlide(data) {
    if (!myJudgeId || !data) return;

    const rankingScreen = document.getElementById('ranking-screen');
    const loginScreen = document.getElementById('login-screen');
    const scoringScreen = document.getElementById('scoring-screen');
    const waitingScreen = document.getElementById('waiting-screen');
    const pkScoringScreen = document.getElementById('pk-scoring-screen');
    const submittedOverlay = document.getElementById('submitted-overlay');
    const pkSubmittedOverlay = document.getElementById('pk-submitted-overlay');

    if (data.slide === 3) {
        if (!screenBeforeLeaderboard) {
            const isVisible = (element) => element && !element.classList.contains('hidden');
            screenBeforeLeaderboard = {
                login: isVisible(loginScreen), waiting: isVisible(waitingScreen),
                scoring: isVisible(scoringScreen), pkScoring: isVisible(pkScoringScreen),
                submitted: isVisible(submittedOverlay), pkSubmitted: isVisible(pkSubmittedOverlay)
            };
        }
        if (scoringScreen) scoringScreen.classList.add('hidden');
        if (pkScoringScreen) pkScoringScreen.classList.add('hidden');
        if (submittedOverlay) submittedOverlay.classList.add('hidden');
        if (pkSubmittedOverlay) pkSubmittedOverlay.classList.add('hidden');
        if (waitingScreen) waitingScreen.classList.add('hidden');

        const titleEl = document.getElementById('ranking-screen-title');
        if (titleEl && data.leaderboard_title) titleEl.innerText = data.leaderboard_title;
        const tbody = document.getElementById('ranking-tbody');
        if (tbody && Array.isArray(data.leaderboard)) {
            tbody.replaceChildren();
            data.leaderboard.forEach((player, index) => {
                const isFlashing = data.flash_row_idx === index;
                const row = document.createElement('div');
                row.style.cssText = 'height:calc(85vh / 8 - 4px);min-height:60px;background-color:#05143a;border:1px solid #0a225c;margin:2px 0;position:relative;display:flex;align-items:center;box-sizing:border-box;width:100%;';
                if (isFlashing) row.classList.add('flashing-row');
                let displayScore = Number(player.score);
                displayScore = Number.isFinite(displayScore) ? displayScore.toFixed(3) : '-';
                const textColor = isFlashing ? '#ffff00' : '#ffffff';

                const rankBadge = document.createElement('div');
                rankBadge.style.cssText = 'position:absolute;left:0;top:0;bottom:0;width:10%;max-width:80px;background-color:#0056cc;clip-path:polygon(0 0,100% 0,75% 100%,0 100%);display:flex;align-items:center;justify-content:center;padding-right:2%;';
                const rankText = document.createElement('span');
                rankText.style.cssText = `color:${textColor};font-family:'Microsoft JhengHei',sans-serif;font-weight:bold;font-size:clamp(16px,3.5vh,28px);z-index:1;`;
                rankText.textContent = player.rank ?? '-';
                rankBadge.appendChild(rankText);

                const name = document.createElement('div');
                name.style.cssText = 'margin-left:12%;margin-right:2%;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;';
                const nameText = document.createElement('span');
                nameText.style.cssText = `color:${textColor};font-family:'Microsoft JhengHei',sans-serif;font-weight:bold;font-size:clamp(16px,3.5vh,28px);`;
                nameText.textContent = player.team ? `${player.name ?? ''} - ${player.team}` : (player.name ?? '');
                name.appendChild(nameText);

                const score = document.createElement('div');
                score.style.cssText = `margin-right:2%;color:${textColor};font-family:'Microsoft JhengHei',sans-serif;font-weight:bold;font-size:clamp(20px,4.5vh,36px);`;
                score.textContent = displayScore;
                row.append(rankBadge, name, score);
                tbody.appendChild(row);
            });
        }
        if (rankingScreen) rankingScreen.classList.remove('hidden');
    } else if (rankingScreen && !rankingScreen.classList.contains('hidden')) {
        rankingScreen.classList.add('hidden');
        const previous = screenBeforeLeaderboard;
        if (previous) {
            const setVisible = (element, visible) => { if (element) element.classList.toggle('hidden', !visible); };
            setVisible(loginScreen, previous.login);
            setVisible(waitingScreen, previous.waiting);
            setVisible(scoringScreen, previous.scoring);
            setVisible(pkScoringScreen, previous.pkScoring);
            setVisible(submittedOverlay, previous.submitted);
            setVisible(pkSubmittedOverlay, previous.pkSubmitted);
        }
        screenBeforeLeaderboard = null;
    }
}

socket.on('projection_slide_changed', applyProjectionSlide);

// ==========================================
// 8. 倒數計時器邏輯 (Countdown Timer Logic)
// ==========================================

// 格式化秒數為 M:SS 格式 (例如 90 -> 1:30, 9 -> 0:09)
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// 啟動倒數計時器 (在被動同步模式下，僅用於手動初始化或重設顯示，不再使用 setInterval 以防與主控端時間衝突抖動)
function startCountdownTimer(startSec = 90) {
    currentCountdownSec = startSec;
    
    const timerValEl = document.getElementById('val-timer');
    if (timerValEl) {
        timerValEl.innerText = formatTime(currentCountdownSec);
        if (currentCountdownSec <= 10) {
            timerValEl.style.color = 'var(--color-danger)';
            timerValEl.style.textShadow = '0 0 12px rgba(255, 51, 102, 0.4)';
        } else {
            timerValEl.style.color = 'var(--color-warning)';
            timerValEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
        }
    }
}

// 停止倒數計時器 (被動同步模式下留空相容)
function stopCountdownTimer() {
    // 留空以防其他相容性呼叫
}

// 監聽後端計時器狀態同步事件 (完全由後端主導，精準更新，絕無抖動)
socket.on('timer_sync', (data) => {
    if (!myJudgeId) return;
    if (data && data.seconds !== undefined) {
        currentCountdownSec = data.seconds;

        // 同步一般評分畫面計時器
        const timerValEl = document.getElementById('val-timer');
        if (timerValEl) {
            timerValEl.innerText = formatTime(currentCountdownSec);
            if (currentCountdownSec <= 10) {
                timerValEl.style.color = 'var(--color-danger)';
                timerValEl.style.textShadow = '0 0 12px rgba(255, 51, 102, 0.4)';
            } else {
                timerValEl.style.color = 'var(--color-warning)';
                timerValEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
            }
        }

        // 同步 PK 評分畫面計時器
        const pkTimerEl = document.getElementById('pk-val-timer');
        if (pkTimerEl) {
            pkTimerEl.innerText = formatTime(currentCountdownSec);
            if (currentCountdownSec <= 10) {
                pkTimerEl.style.color = 'var(--color-danger)';
                pkTimerEl.style.textShadow = '0 0 12px rgba(255, 51, 102, 0.4)';
            } else {
                pkTimerEl.style.color = 'var(--color-warning)';
                pkTimerEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
            }
        }
    }
});

// ==========================================
// 9. PK 同時上場 評分邏輯 (PK Simultaneous Scoring)
// ==========================================

// PK 雙方評分狀態
let pkScores = {
    chung: { cntMinor: 0, cntMajor: 0, p1: 2.0, p2: 2.0, p3: 2.0 },
    hong:  { cntMinor: 0, cntMajor: 0, p1: 2.0, p2: 2.0, p3: 2.0 }
};

// 快速評分暫存（送出前的選取值）
let pkQuickAccPending = { chung: null, hong: null };
let pkQuickPresPending = { chung: { p1: null, p2: null, p3: null }, hong: { p1: null, p2: null, p3: null } };

// ── 重置 PK 評分資料與 UI ──
function pkResetScoringData() {
    pkScores = {
        chung: { cntMinor: 0, cntMajor: 0, p1: 2.0, p2: 2.0, p3: 2.0 },
        hong:  { cntMinor: 0, cntMajor: 0, p1: 2.0, p2: 2.0, p3: 2.0 }
    };
    pkUpdateAllUI();
}

// ── 更新所有 PK UI ──
function pkUpdateAllUI() {
    ['chung', 'hong'].forEach(side => {
        const s = pkScores[side];
        document.getElementById(`pk-${side}-cnt-minor`).innerText = s.cntMinor;
        document.getElementById(`pk-${side}-cnt-major`).innerText = s.cntMajor;
        document.getElementById(`pk-${side}-val-p1`).innerText = s.p1.toFixed(1);
        document.getElementById(`pk-${side}-val-p2`).innerText = s.p2.toFixed(1);
        document.getElementById(`pk-${side}-val-p3`).innerText = s.p3.toFixed(1);
    });
    pkUpdateTotals();
}

// ── 計算並更新雙方總分顯示 ──
function pkUpdateTotals() {
    ['chung', 'hong'].forEach(side => {
        const s = pkScores[side];
        let acc = 4.0 - (s.cntMinor * 0.1) - (s.cntMajor * 0.3);
        if (acc < 0) acc = 0;
        acc = parseFloat(acc.toFixed(1));

        const pres = parseFloat((s.p1 + s.p2 + s.p3).toFixed(1));
        const total = parseFloat((acc + pres).toFixed(1));

        document.getElementById(`pk-${side}-val-acc`).innerText = acc.toFixed(1);
        document.getElementById(`pk-${side}-val-pres`).innerText = pres.toFixed(1);
        document.getElementById(`pk-${side}-total`).innerText = total.toFixed(1);
        document.getElementById(`pk-${side}-bottom-total`).innerText = total.toFixed(1);
    });
    syncScoreDraft();
}

// ── 扣分 ──
function pkDeductAccuracy(side, value) {
    if (value === 0.1) {
        pkScores[side].cntMinor++;
        document.getElementById(`pk-${side}-cnt-minor`).innerText = pkScores[side].cntMinor;
        triggerVibrate(40);
    } else if (value === 0.3) {
        pkScores[side].cntMajor++;
        document.getElementById(`pk-${side}-cnt-major`).innerText = pkScores[side].cntMajor;
        triggerVibrate(90);
    }
    pkUpdateTotals();
}

// ── 退回扣分 ──
function pkUndoDeduct(side, value) {
    if (value === 0.1 && pkScores[side].cntMinor > 0) {
        pkScores[side].cntMinor--;
        document.getElementById(`pk-${side}-cnt-minor`).innerText = pkScores[side].cntMinor;
        triggerVibrate(20);
    } else if (value === 0.3 && pkScores[side].cntMajor > 0) {
        pkScores[side].cntMajor--;
        document.getElementById(`pk-${side}-cnt-major`).innerText = pkScores[side].cntMajor;
        triggerVibrate(20);
    }
    pkUpdateTotals();
}

// ── 調整表現性細項 ──
function pkAdjustPres(side, field, delta) {
    let val = parseFloat((pkScores[side][field] + delta).toFixed(1));
    if (val >= 0.0 && val <= 2.0) {
        pkScores[side][field] = val;
        document.getElementById(`pk-${side}-val-${field}`).innerText = val.toFixed(1);
        triggerVibrate(delta > 0 ? 30 : 20);
        pkUpdateTotals();
    }
}

// ── 計算某一側的得分摘要 ──
function pkCalcSideScore(side) {
    const s = pkScores[side];
    let acc = 4.0 - (s.cntMinor * 0.1) - (s.cntMajor * 0.3);
    if (acc < 0) acc = 0;
    acc = parseFloat(acc.toFixed(1));
    const pres = parseFloat((s.p1 + s.p2 + s.p3).toFixed(1));
    const total = parseFloat((acc + pres).toFixed(1));
    return { acc, pres, total, p1: s.p1, p2: s.p2, p3: s.p3 };
}

// ── 送出雙方分數 ──
function pkSubmitBothScores() {
    const chung = pkCalcSideScore('chung');
    const hong  = pkCalcSideScore('hong');

    // 依序送出：先青方（player_side=0），後紅方（player_side=1）
    socket.emit('pk_submit_score', {
        chung: { accuracy: chung.acc, presentation: chung.pres, p1: chung.p1, p2: chung.p2, p3: chung.p3 },
        hong:  { accuracy: hong.acc,  presentation: hong.pres,  p1: hong.p1,  p2: hong.p2,  p3: hong.p3  }
    });

    stopCountdownTimer();

    // 更新送出覆蓋層
    document.getElementById('pk-submitted-chung-total').innerText = chung.total.toFixed(1);
    document.getElementById('pk-submitted-chung-acc').innerText = chung.acc.toFixed(1);
    document.getElementById('pk-submitted-chung-pres').innerText = chung.pres.toFixed(1);
    document.getElementById('pk-submitted-hong-total').innerText = hong.total.toFixed(1);
    document.getElementById('pk-submitted-hong-acc').innerText = hong.acc.toFixed(1);
    document.getElementById('pk-submitted-hong-pres').innerText = hong.pres.toFixed(1);

    document.getElementById('pk-submitted-overlay').classList.remove('hidden');
    // 確保「修改分數」按鈕正常顯示
    const pkBtnModify = document.getElementById('pk-btn-modify-score');
    if (pkBtnModify) {
        pkBtnModify.classList.remove('hidden');
    }
    triggerVibrate([50, 100, 50]);
}

// ── 修改已送出的 PK 分數 ──
function pkModifyScore() {
    document.getElementById('pk-submitted-overlay').classList.add('hidden');
    socket.emit('modify_score');
    triggerVibrate(30);
}

// ── 進入 PK 同時上場評分畫面 ──
function showPkScoringScreen(data) {
    currentMode = 1;
    currentStage = data.stage !== undefined ? data.stage : 1;
    currentPkSequenceMode = data.pk_sequence_mode !== undefined ? data.pk_sequence_mode : 0;
    currentPlayerSide = data.player_side !== undefined ? data.player_side : 0;

    // 填入頂部資訊
    document.getElementById('pk-info-type').innerText = data.match_type || '---';
    document.getElementById('pk-info-category').innerText = data.category || '---';
    document.getElementById('pk-info-division').innerText = data.division || '---';
    document.getElementById('pk-info-phase').innerText = data.phase || '---';
    document.getElementById('pk-display-judge-id-live').innerText = myJudgeId;

    // 型場標籤（跟一般賽制相同：R1/R2 雙標籤，只顯示當前 stage）
    const pkTagR1 = document.getElementById('pk-poomsae-stage-r1');
    const pkTagR2 = document.getElementById('pk-poomsae-stage-r2');
    const pkInfoR1 = document.getElementById('pk-info-poomsae-r1');
    const pkInfoR2 = document.getElementById('pk-info-poomsae-r2');
    if (pkInfoR1) pkInfoR1.innerHTML = formatPoomsaeText(data.poomsae_1 || '---');
    if (data.poomsae_2 && !data.poomsae_2.includes('不需選擇')) {
        if (pkInfoR2) pkInfoR2.innerHTML = formatPoomsaeText(data.poomsae_2);
    } else {
        if (pkInfoR2) pkInfoR2.innerText = '';
    }
    // 高亮當前 stage，隱藏另一個
    if (pkTagR1 && pkTagR2) {
        pkTagR1.classList.remove('active-stage', 'hidden');
        pkTagR2.classList.remove('active-stage', 'hidden');
        if (data.stage === 2 && data.poomsae_2 && !data.poomsae_2.includes('不需選擇')) {
            pkTagR1.classList.add('hidden');
            pkTagR2.classList.add('active-stage');
        } else {
            pkTagR1.classList.add('active-stage');
            pkTagR2.classList.add('hidden');
        }
    }

    // 青方資訊
    document.getElementById('pk-chung-team').innerText = data.chung_team || data.team || '---';
    document.getElementById('pk-chung-name').innerText = data.chung_player || data.player || '---';

    // 紅方資訊
    document.getElementById('pk-hong-team').innerText = data.hong_team || '---';
    document.getElementById('pk-hong-name').innerText = data.hong_player || '---';

    // 重置分數
    pkResetScoringData();

    // 重置送出覆蓋層
    document.getElementById('pk-submitted-overlay').classList.add('hidden');

    // 初始化計時器顯示
    const pkTimerEl = document.getElementById('pk-val-timer');
    if (pkTimerEl) {
        pkTimerEl.innerText = '1:30';
        pkTimerEl.style.color = 'var(--color-warning)';
        pkTimerEl.style.textShadow = '0 0 12px rgba(255, 204, 0, 0.4)';
    }

    // 切換畫面
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('waiting-screen').classList.add('hidden');
    document.getElementById('scoring-screen').classList.add('hidden');
    const rankingScreen = document.getElementById('ranking-screen');
    if (rankingScreen) rankingScreen.classList.add('hidden');
    document.getElementById('pk-scoring-screen').classList.remove('hidden');

    requestWakeLock();
    triggerVibrate(80);
}

// ==========================================
// PK 快速評分 Modal（正確性）
// ==========================================

let pkQuickAccTempValue = { chung: null, hong: null };

function pkOpenQuickAcc(side) {
    const gridId = `pk-quick-acc-${side}-grid`;
    const grid = document.getElementById(gridId);
    if (!grid) return;

    // 計算當前正確性分數
    const s = pkScores[side];
    let currentAcc = parseFloat((4.0 - (s.cntMinor * 0.1) - (s.cntMajor * 0.3)).toFixed(1));
    if (currentAcc < 0) currentAcc = 0;

    grid.innerHTML = '';
    pkQuickAccTempValue[side] = currentAcc;

    // 生成 0.0 ~ 4.0 的按鈕（每 0.1 一格，從小到大）
    for (let v = 0; v <= 40; v++) {
        const score = parseFloat((v / 10).toFixed(1));
        const btn = document.createElement('button');
        btn.className = 'btn-quick-num' + (Math.abs(score - currentAcc) < 0.001 ? ' selected' : '');
        btn.innerText = score.toFixed(1);
        if (score === 4.0) {
            btn.classList.add('span-all');
        }
        btn.onclick = () => {
            grid.querySelectorAll('.btn-quick-num').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            pkQuickAccTempValue[side] = score;
        };
        grid.appendChild(btn);
    }

    document.getElementById(`pk-quick-acc-${side}-modal`).classList.remove('hidden');
    triggerVibrate(20);
}

function pkConfirmQuickAcc(side) {
    const chosen = pkQuickAccTempValue[side];
    if (chosen !== null) {
        // 將正確性分數換算為 minor 扣分次數（major 清零）
        const deduct = parseFloat((4.0 - chosen).toFixed(1));
        pkScores[side].cntMajor = 0;
        pkScores[side].cntMinor = Math.max(0, Math.round(deduct / 0.1));
        document.getElementById(`pk-${side}-cnt-minor`).innerText = pkScores[side].cntMinor;
        document.getElementById(`pk-${side}-cnt-major`).innerText = pkScores[side].cntMajor;
        pkUpdateTotals();
    }
    document.getElementById(`pk-quick-acc-${side}-modal`).classList.add('hidden');
    triggerVibrate(50);
}

function pkCancelQuickAcc(side) {
    document.getElementById(`pk-quick-acc-${side}-modal`).classList.add('hidden');
    triggerVibrate(20);
}

// ==========================================
// PK 快速評分 Modal（表現性）
// ==========================================

let pkQuickPresTempValue = {
    chung: { p1: null, p2: null, p3: null },
    hong:  { p1: null, p2: null, p3: null }
};

function pkOpenQuickPres(side) {
    const fieldPairs = [
        { field: 'p1', currentId: `pk-${side}-quick-p1-current`, gridId: `pk-${side}-quick-p1-grid` },
        { field: 'p2', currentId: `pk-${side}-quick-p2-current`, gridId: `pk-${side}-quick-p2-grid` },
        { field: 'p3', currentId: `pk-${side}-quick-p3-current`, gridId: `pk-${side}-quick-p3-grid` }
    ];

    fieldPairs.forEach(({ field, currentId, gridId }) => {
        const currentVal = pkScores[side][field];
        pkQuickPresTempValue[side][field] = currentVal;

        const currentSpan = document.getElementById(currentId);
        if (currentSpan) currentSpan.innerText = currentVal.toFixed(1);

        const grid = document.getElementById(gridId);
        if (!grid) return;
        grid.innerHTML = '';

        // 生成 0.0 ~ 2.0 的按鈕（每 0.1 一格，從小到大）
        for (let v = 0; v <= 20; v++) {
            const score = parseFloat((v / 10).toFixed(1));
            const btn = document.createElement('button');
            btn.className = 'btn-quick-num' + (Math.abs(score - currentVal) < 0.001 ? ' selected' : '');
            btn.innerText = score.toFixed(1);
            btn.onclick = () => {
                grid.querySelectorAll('.btn-quick-num').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                pkQuickPresTempValue[side][field] = score;
            };
            grid.appendChild(btn);
        }
    });

    document.getElementById(`pk-quick-pres-${side}-modal`).classList.remove('hidden');
    triggerVibrate(20);
}

function pkConfirmQuickPres(side) {
    ['p1', 'p2', 'p3'].forEach(field => {
        const chosen = pkQuickPresTempValue[side][field];
        if (chosen !== null) {
            pkScores[side][field] = chosen;
            document.getElementById(`pk-${side}-val-${field}`).innerText = chosen.toFixed(1);
        }
    });
    pkUpdateTotals();
    document.getElementById(`pk-quick-pres-${side}-modal`).classList.add('hidden');
    triggerVibrate(50);
}

function pkCancelQuickPres(side) {
    document.getElementById(`pk-quick-pres-${side}-modal`).classList.add('hidden');
    triggerVibrate(20);
}

// ── pk_scoring_start 事件處理（僅在同時上場模式下跳轉 PK 雙側介面）──
// 若為交叉/依序上場，此事件不應被觸發（web_server 會發 scoring_start）
// 此 handler 作為備用保護：即使收到 pk_scoring_start，也會依 pkSeqMode 正確分流
socket.on('pk_scoring_start', (data) => {
    if (!myJudgeId) return;
    try {
        const pkSeqMode = data.pk_sequence_mode !== undefined ? data.pk_sequence_mode : 0;
        if (pkSeqMode === 0) {
            // 同時上場：顯示 PK 雙側評分介面
            showPkScoringScreen(data);
        } else {
            // 交叉/依序上場：直接觸發前端 scoring_start 事件（防禦性 fallback）
            socket.emit('scoring_start', data);
            // 後端不應走到這裡，這裡備用直接觸發本地 handler
            const evt = new CustomEvent('_local_scoring_start', { detail: data });
            document.dispatchEvent(evt);
        }
    } catch (err) {
        console.error('pk_scoring_start 錯誤:', err);
    }
});
