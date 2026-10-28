/* 停车场出入口 3D 视图
 *
 * 职责：
 *   1. 加载 Blender 导出的 resources/model/parking.glb（含动画与机位空物体）
 *   2. 没有模型时退化为内置演示场景，保证界面不空
 *   3. 对外暴露 window.DSHParking.trigger(gate, action)：
 *        镜头飞回该道闸的摄像机位 → 播对应动画 → 播完回调 Python
 *
 * 与 Python 的约定：
 *   Python → JS: DSHParking.trigger('in'|'out', 'open'|'close')
 *   JS → Python: bridge.onStage(gate, stage)   stage = 'focus' | 'action'
 *                bridge.onFinished(gate, action)
 *                bridge.onReady(mode)          mode = 'model' | 'demo'
 *                bridge.onError(message)
 */
(function () {
  'use strict';

  // r147 默认是 legacy 色彩管线：十六进制颜色会被当成线性值再转 sRGB，
  // 视觉上会整体发白。开启色彩管理后，颜色按 sRGB 解释，和界面配色一致。
  if (THREE.ColorManagement) THREE.ColorManagement.legacyMode = false;

  var CFG = {
    bg: 0xe8eff7,
    model: '../resources/model/parking.glb',
    focusSeconds: 0.9,
    actionSeconds: 1.8,      // 动画统一压到这个时长，避免 10 秒的慢动作
    fov: 46,
    anchors: { 'in': 'cam_in', 'out': 'cam_out', wide: 'cam_wide' }
  };

  var bridge = null;
  var scene, camera, renderer, clock, mixer;
  var root = null;                 // glb 根节点（或演示场景）
  var actions = {};                // '{gate}_{action}' -> AnimationAction
  var demoGates = {};              // 演示场景中可旋转的闸杆
  var anchors = {};                // 机位 {in: {pos, quat}, out: {...}, wide: {...}}
  var tween = null;                // 镜头过渡
  var acting = null;               // 当前动作
  var demoAnim = null;             // 演示场景的闸杆补间
  var actingTimer = null;          // 动画完成兜底定时器
  var mode = 'demo';
  var resizeObserver = null;

  // ------------------------------------------------------------ 工具
  function send(fn) {
    var args = Array.prototype.slice.call(arguments, 1);
    if (bridge && typeof bridge[fn] === 'function') {
      try { bridge[fn].apply(bridge, args); } catch (e) { /* 忽略桥接异常 */ }
    }
  }

  function log(msg) {
    if (window.console) console.log('[3d] ' + msg);
  }

  function easeInOut(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  // ------------------------------------------------------------ 场景
  function initScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(CFG.bg);
    scene.fog = new THREE.Fog(CFG.bg, 22, 46);

    camera = new THREE.PerspectiveCamera(CFG.fov, 16 / 9, 0.1, 200);
    camera.position.set(0, 6, 14);

    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.toneMappingExposure = 1.0;
    document.body.appendChild(renderer.domElement);

    var hemi = new THREE.HemisphereLight(0xffffff, 0xdfe8f0, 0.95);
    scene.add(hemi);
    var key = new THREE.DirectionalLight(0xffffff, 1.45);
    key.position.set(6, 10, 6);
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xbcd3e8, 0.45);
    fill.position.set(-8, 6, -6);
    scene.add(fill);

    var lamp = new THREE.PointLight(0xffffff, 0.9, 26, 2);
    lamp.position.set(-3.5, 5.2, 3.5);
    scene.add(lamp);

    clock = new THREE.Clock();
    resize();
    window.addEventListener('resize', resize);
    if (typeof ResizeObserver === 'function') {
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(document.documentElement);
    }
    animate();
  }

  function resize() {
    var w = Math.max(1, document.documentElement.clientWidth || window.innerWidth || 640);
    var h = Math.max(1, document.documentElement.clientHeight || window.innerHeight || 360);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, true);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  // ------------------------------------------------------------ 演示场景
  function buildDemoScene() {
    mode = 'demo';
    var g = new THREE.Group();

    var ground = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 40),
      new THREE.MeshStandardMaterial({ color: 0xdce6f0, roughness: 0.95, metalness: 0.0 })
    );
    ground.rotation.x = -Math.PI / 2;
    g.add(ground);

    var grid = new THREE.GridHelper(60, 60, 0xc3d3e3, 0xd6e1ec);
    grid.position.y = 0.01;
    g.add(grid);

    // 车道
    var lane = new THREE.Mesh(
      new THREE.PlaneGeometry(24, 5.2),
      new THREE.MeshStandardMaterial({ color: 0xcfdbe7, roughness: 0.9 })
    );
    lane.rotation.x = -Math.PI / 2;
    lane.position.set(0, 0.02, 1.6);
    g.add(lane);

    // 岗亭
    var booth = new THREE.Mesh(
      new THREE.BoxGeometry(2.2, 2.0, 2.0),
      new THREE.MeshStandardMaterial({ color: 0xf4f8fc, roughness: 0.7, metalness: 0.1 })
    );
    booth.position.set(0, 1.0, -1.6);
    g.add(booth);

    ['in', 'out'].forEach(function (gate, i) {
      var x = i === 0 ? -4.2 : 4.2;
      var grp = new THREE.Group();
      grp.position.set(x, 0, 1.2);

      var post = new THREE.Mesh(
        new THREE.BoxGeometry(0.34, 2.3, 0.34),
        new THREE.MeshStandardMaterial({ color: 0x3b5f80, roughness: 0.45, metalness: 0.3 })
      );
      post.position.y = 1.15;
      grp.add(post);

      var head = new THREE.Mesh(
        new THREE.BoxGeometry(0.5, 0.42, 0.5),
        new THREE.MeshStandardMaterial({ color: 0x2f5372, roughness: 0.4, metalness: 0.3 })
      );
      head.position.y = 2.4;
      grp.add(head);

      // 闸杆：以立柱顶端为轴心，绕 Z 轴抬起
      var pivot = new THREE.Group();
      pivot.position.set(0, 2.25, 0);
      grp.add(pivot);

      var arm = new THREE.Mesh(
        new THREE.BoxGeometry(3.4, 0.14, 0.14),
        new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.35, metalness: 0.2 })
      );
      arm.position.x = 1.7;
      pivot.add(arm);

      for (var s = 0; s < 4; s++) {
        var stripe = new THREE.Mesh(
          new THREE.BoxGeometry(0.34, 0.16, 0.16),
          new THREE.MeshStandardMaterial({ color: 0xff5c6c, roughness: 0.5 })
        );
        stripe.position.set(0.5 + s * 0.8, 0, 0);
        pivot.add(stripe);
      }

      demoGates[gate] = pivot;
      g.add(grp);
    });

    root = g;
    scene.add(g);
    buildDemoAnchors();

    var hint = document.getElementById('hint');
    hint.style.display = 'block';
    hint.textContent = '演示模型 · 放入 resources/model/parking.glb 替换';
    return g;
  }

  function buildDemoAnchors() {
    anchors = {
      'in': lookFrom(new THREE.Vector3(-8.2, 3.9, 9.0), new THREE.Vector3(-3.9, 2.9, 1.0)),
      'out': lookFrom(new THREE.Vector3(8.2, 3.9, 9.0), new THREE.Vector3(3.9, 2.9, 1.0)),
      wide: lookFrom(new THREE.Vector3(0, 7.2, 15.5), new THREE.Vector3(0, 1.2, 0.5))
    };
  }

  // 注意：相机朝向是 -Z，Object3D.lookAt 是 +Z，必须用相机来算四元数
  function lookFrom(pos, target) {
    var cam = new THREE.PerspectiveCamera();
    cam.position.copy(pos);
    cam.lookAt(target);
    return { pos: pos.clone(), quat: cam.quaternion.clone(), look: target.clone() };
  }

  // ------------------------------------------------------------ glTF
  function loadModel() {
    var loader = new THREE.GLTFLoader();
    loader.load(CFG.model, function (gltf) {
      mode = 'model';
      root = gltf.scene;
      root.traverse(function (o) {
        if (o.isMesh) {
          o.castShadow = false;
          o.receiveShadow = false;
          if (o.material) o.material.side = THREE.FrontSide;
        }
      });
      scene.add(root);
      addModelGround();
      prepareModelAnchors(gltf);
      prepareClips(gltf);
      document.getElementById('loading').style.display = 'none';
      if (anchors.wide) {
        camera.position.copy(anchors.wide.pos);
        camera.quaternion.copy(anchors.wide.quat);
      }
      log('model loaded, clips=' + gltf.animations.length);
      send('onReady', mode);
    }, function () { /* progress */ }, function (err) {
      log('model missing, fallback to demo: ' + err);
      finishDemo('未找到 parking.glb，使用演示模型');
    });
  }

  function finishDemo(reason) {
    if (document.getElementById('loading')) {
      document.getElementById('loading').style.display = 'none';
    }
    buildDemoScene();
    send('onReady', mode);
    if (reason) log(reason);
  }

  function addModelGround() {
    var box = new THREE.Box3().setFromObject(root);
    var minY = isFinite(box.min.y) ? box.min.y : 0;
    var ground = new THREE.Mesh(
      new THREE.PlaneGeometry(240, 240),
      new THREE.MeshStandardMaterial({ color: 0xdfe8f2, roughness: 1.0, metalness: 0.0 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = minY - 0.02;
    scene.add(ground);
  }

  function prepareModelAnchors(gltf) {
    ['in', 'out', 'wide'].forEach(function (key) {
      var obj = null;
      root.traverse(function (o) {
        if (!obj && o.name === CFG.anchors[key]) obj = o;
      });
      if (!obj) return;

      var pos = new THREE.Vector3();
      var quat = new THREE.Quaternion();
      obj.getWorldPosition(pos);
      obj.getWorldQuaternion(quat);

      // 若放的是摄像机（Camera），直接用它的机位与朝向；
      // 若放的是空物体（Empty），没有朝向语义，就让它看向场景中心。
      anchors[key] = {
        pos: pos.clone(),
        quat: quat.clone(),
        lookAtScene: !obj.isCamera,
        look: obj.isCamera ? null : new THREE.Vector3(0, 1, 0)
      };
      if (obj.isCamera) obj.visible = false;
    });

    // 没有摄像机锚点时，直接按 gate_in / gate_out 节点生成机位
    ['in', 'out'].forEach(function (key) {
      if (anchors[key]) return;
      var g = root.getObjectByName('gate_' + key);
      if (!g) return;
      var pos = new THREE.Vector3();
      g.getWorldPosition(pos);
      var sign = key === 'in' ? 1 : -1;
      var camPos = new THREE.Vector3(pos.x + sign * 2.6, pos.y + 2.2, pos.z + 4.4);
      var look = new THREE.Vector3(pos.x, pos.y + 1.1, pos.z);
      anchors[key] = lookFrom(camPos, look);
    });

    if (!anchors.wide) {
      var wbox = new THREE.Box3().setFromObject(root);
      var wsize = wbox.getSize(new THREE.Vector3());
      var wc = wbox.getCenter(new THREE.Vector3());
      anchors.wide = lookFrom(
        new THREE.Vector3(wc.x + wsize.x * 0.15, wc.y + wsize.y * 0.9, wc.z + Math.max(wsize.z, wsize.x) * 1.15),
        new THREE.Vector3(wc.x, wc.y + wsize.y * 0.15, wc.z)
      );
    }

    if (!anchors['in'] || !anchors['out']) {
      var box = new THREE.Box3().setFromObject(root);
      var size = box.getSize(new THREE.Vector3());
      var center = box.getCenter(new THREE.Vector3());
      anchors['in'] = lookFrom(
        new THREE.Vector3(center.x - size.x * 0.45, size.y * 0.8 + 1.2, center.z + size.z * 1.4),
        new THREE.Vector3(center.x - size.x * 0.2, size.y * 0.35, center.z)
      );
      anchors['out'] = lookFrom(
        new THREE.Vector3(center.x + size.x * 0.45, size.y * 0.8 + 1.2, center.z + size.z * 1.4),
        new THREE.Vector3(center.x + size.x * 0.2, size.y * 0.35, center.z)
      );
      anchors.wide = lookFrom(
        new THREE.Vector3(center.x, size.y + 4, center.z + Math.max(size.z, size.x) * 1.6),
        center
      );
    }
  }

  function prepareClips(gltf) {
    mixer = new THREE.AnimationMixer(root);
    var patterns = {
      'in_open': /gate[-_ ]?in[-_ ]?(open|up)/i,
      'in_close': /gate[-_ ]?in[-_ ]?(close|down)/i,
      'out_open': /gate[-_ ]?out[-_ ]?(open|up)/i,
      'out_close': /gate[-_ ]?out[-_ ]?(close|down)/i
    };
    gltf.animations.forEach(function (clip) {
      Object.keys(patterns).forEach(function (key) {
        if (!actions[key] && patterns[key].test(clip.name)) {
          var act = mixer.clipAction(clip);
          act.setLoop(THREE.LoopOnce, 1);
          act.clampWhenFinished = true;
          actions[key] = act;
          log('clip "' + clip.name + '" -> ' + key);
        }
      });
    });
    mixer.addEventListener('finished', function () {
      if (acting) {
        var done = acting;
        acting = null;
        send('onFinished', done.gate, done.action);
      }
    });
  }

  // ------------------------------------------------------------ 镜头
  function flyTo(key, seconds, onDone) {
    var target = anchors[key];
    if (!target) { if (onDone) onDone(); return; }
    var toPos = target.pos.clone();
    if (target.look && target.lookAtScene) {
      // 画面越窄，镜头退得越远，保证道闸完整入镜
      var pull = Math.max(1, 1.45 / Math.max(0.55, camera.aspect));
      toPos = target.look.clone().add(
        target.pos.clone().sub(target.look).multiplyScalar(pull)
      );
    }

    var q = target.quat.clone();
    if (target.lookAtScene) {
      var cam = new THREE.PerspectiveCamera();
      cam.position.copy(target.pos);
      cam.lookAt(new THREE.Vector3(0, 1, 0));
      q = cam.quaternion.clone();
    }
    tween = {
      t: 0,
      dur: seconds,
      fromPos: camera.position.clone(),
      toPos: toPos,
      fromQuat: camera.quaternion.clone(),
      toQuat: q,
      done: onDone
    };
  }

  function updateTween(dt) {
    if (!tween) return;
    tween.t = Math.min(1, tween.t + dt / tween.dur);
    var k = easeInOut(tween.t);
    camera.position.lerpVectors(tween.fromPos, tween.toPos, k);
    camera.quaternion.copy(tween.fromQuat).slerp(tween.toQuat, k);
    if (tween.t >= 1) {
      var cb = tween.done;
      tween = null;
      if (cb) cb();
    }
  }

  // ------------------------------------------------------------ 动作
  function playAction(gate, action) {
    var key = gate + '_' + action;
    acting = { gate: gate, action: action };

    if (mode === 'model' && actions[key]) {
      Object.keys(actions).forEach(function (k) {
        if (k !== key) actions[k].stop();
      });
      var act = actions[key];
      act.reset();
      act.setEffectiveWeight(1);
      // 导出时往往按整条时间轴（比如 10 秒）出动画，这里按动作时长压缩到 1.8 秒
      var dur = act.getClip().duration || CFG.actionSeconds;
      act.timeScale = Math.min(8, Math.max(0.2, dur / CFG.actionSeconds));
      act.play();

      // 兜底：个别情况下 mixer 的 finished 不触发，用定时器补一次
      if (actingTimer) clearTimeout(actingTimer);
      actingTimer = setTimeout(function () {
        if (acting && acting.gate === gate && acting.action === action) {
          var done = acting;
          acting = null;
          send('onFinished', done.gate, done.action);
        }
      }, (dur / act.timeScale) * 1000 + 500);
      return;
    }

    // 演示场景：直接补间闸杆角度
    var pivot = demoGates[gate];
    if (!pivot) { acting = null; send('onFinished', gate, action); return; }
    var from = pivot.rotation.z;
    var to = action === 'open' ? Math.PI * 85 / 180 : 0;
    demoAnim = { t: 0, dur: CFG.actionSeconds, from: from, to: to, gate: gate, action: action };
  }

  function updateDemoAnim(dt) {
    if (!demoAnim) return;
    demoAnim.t = Math.min(1, demoAnim.t + dt / demoAnim.dur);
    var k = easeInOut(demoAnim.t);
    demoGates[demoAnim.gate].rotation.z = demoAnim.from + (demoAnim.to - demoAnim.from) * k;
    if (demoAnim.t >= 1) {
      var done = demoAnim;
      demoAnim = null;
      acting = null;
      send('onFinished', done.gate, done.action);
    }
  }

  // ------------------------------------------------------------ 主循环
  function animate() {
    requestAnimationFrame(animate);
    var dt = Math.min(clock.getDelta(), 0.05);
    updateTween(dt);
    if (mixer) mixer.update(dt);
    updateDemoAnim(dt);
    renderer.render(scene, camera);
  }

  // ------------------------------------------------------------ 对外 API
  var API = {
    trigger: function (gate, action) {
      if (!anchors[gate]) {
        send('onError', '缺少机位：' + gate);
        return;
      }
      send('onStage', gate, 'focus');
      flyTo(gate, CFG.focusSeconds, function () {
        send('onStage', gate, 'action');
        playAction(gate, action);
      });
    },

    preview: function () {
      flyTo('wide', CFG.focusSeconds, null);
    },

    snapshot: function () {
      try { return renderer.domElement.toDataURL('image/png'); } catch (e) { return ''; }
    },

    info: function () {
      return JSON.stringify({
        mode: mode,
        gates: Object.keys(demoGates),
        clips: Object.keys(actions),
        anchors: Object.keys(anchors)
      });
    }
  };
  window.DSHParking = API;

  // ------------------------------------------------------------ 启动
  function start() {
    initScene();
    if (typeof THREE.GLTFLoader !== 'function') {
      finishDemo('未加载 GLTFLoader，使用演示模型');
      return;
    }
    var loader = new THREE.GLTFLoader();
    var probe = new XMLHttpRequest();
    probe.open('HEAD', CFG.model, true);
    probe.onreadystatechange = function () {
      if (probe.readyState !== 4) return;
      if (probe.status >= 200 && probe.status < 400) {
        loadModel();
      } else {
        finishDemo('未找到 ' + CFG.model);
      }
    };
    probe.onerror = function () { finishDemo('模型探测失败'); };
    probe.send();
  }

  if (typeof qt !== 'undefined' && qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.bridge;
      start();
    });
  } else {
    start();
  }
})();
