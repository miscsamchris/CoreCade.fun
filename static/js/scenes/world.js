function setWorld(worldState) {
    console.log(worldState);
    function makeTile(type) {
      return [sprite("tile"), { type }];
    }
  
    const map = [
      addLevel(
        [
          "                            ",
          " cddddddddddddddddddddddddde",
          " 300000000000000000000000002",
          " 300000000000000000000000002",
          " 300000000000000000000000002",
          " 307777777777777777777777702",
          " 307777777777777777777777702",
          " 300000000000000000000000002",
          " 300000000000000000000000002",
          " 300000000000000000000000002",
          " 111111111111111111111111111",
        ],
        {
          tileWidth: 16,
          tileHeight: 16,
          tiles: {
            0: () => makeTile("grass-m"),
            1: () => makeTile("grass-water"),
            2: () => makeTile("grass-r"),
            3: () => makeTile("grass-l"),
            4: () => makeTile("ground-m"),
            5: () => makeTile("ground-r"),
            6: () => makeTile("ground-l"),
            7: () => makeTile("sand-1"),
            8: () => makeTile("grass-mb"),
            9: () => makeTile("grass-br"),
            a: () => makeTile("grass-bl"),
            b: () => makeTile("rock-water"),
            c: () => makeTile("grass-tl"),
            d: () => makeTile("grass-tm"),
            e: () => makeTile("grass-tr"),
          },
        }
      ),

      addLevel(
        [
          "00000000000000000000000000000",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "0                           0",
          "00000000000000000000000000000",
        ],
        {
          tileWidth: 16,
          tileHeight: 16,
          tiles: {
            0: () => [
              area({ shape: new Rect(vec2(0), 16, 16) }),
              body({ isStatic: true }),
            ],
            1: () => [
              area({
                shape: new Rect(vec2(0), 8, 8),
                offset: vec2(4, 4),
              }),
              body({ isStatic: true }),
            ],
            2: () => [
              area({ shape: new Rect(vec2(0), 2, 16) }),
              body({ isStatic: true }),
            ],
            3: () => [
              area({
                shape: new Rect(vec2(0), 16, 20),
                offset: vec2(0, -4),
              }),
              body({ isStatic: true }),
            ],
          },
        }
      ),
    ];
  
    for (const layer of map) {
      layer.use(scale(4));
      for (const tile of layer.children) {
        if (tile.type) {
          tile.play(tile.type);
        }
      }
    }
  
    const player = add([
      sprite("player-down"),
      pos(100,350),
      scale(4),
      area(),
      body(),
      {
        currentSprite: "player-down",
        speed: 300,
        isInDialogue: false,
      },
    ]);
      add([
      sprite("door"),
      scale(4),
      pos(400, 200),
      area(),
      body({ isStatic: true }),
      "door",
    ]);
  
    let tick = 0;
    onUpdate(() => {
      camPos(player.pos);
      tick++;
      if (
        (isKeyDown("down") || isKeyDown("up")) &&
        tick % 20 === 0 &&
        !player.isInDialogue
      ) {
        player.flipX = !player.flipX;
      }
    });
  
    function setSprite(player, spriteName) {
      if (player.currentSprite !== spriteName) {
        player.use(sprite(spriteName));
        player.currentSprite = spriteName;
      }
    }
  
    onKeyDown("down", () => {
      if (player.isInDialogue) return;
      setSprite(player, "player-down");
      player.move(0, player.speed);
    });
  
    onKeyDown("up", () => {
      if (player.isInDialogue) return;
      setSprite(player, "player-up");
      player.move(0, -player.speed);
    });
  
    onKeyDown("left", () => {
      if (player.isInDialogue) return;
      player.flipX = false;
      if (player.curAnim() !== "walk") {
        setSprite(player, "player-side");
        player.play("walk");
      }
      player.move(-player.speed, 0);
    });
  
    onKeyDown("right", () => {
      if (player.isInDialogue) return;
      player.flipX = true;
      if (player.curAnim() !== "walk") {
        setSprite(player, "player-side");
        player.play("walk");
      }
      player.move(player.speed, 0);
    });
  
    onKeyRelease("left", () => {
      player.stop();
    });
  
    onKeyRelease("right", () => {
      player.stop();
    });
  
    if (!worldState) {
      worldState = {
        playerPos: player.pos,
        faintedMons: [],
      };
    }
  
    player.pos = vec2(worldState.playerPos);
    for (const faintedMon of worldState.faintedMons) {
      destroy(get(faintedMon)[0]);
    }
    let sessionId = null; // Store the session ID for ongoing chat

    function openChatModal(initialMessage, session) {
      player.isInDialogue = true;
      let inputText = "";
      let messages = [`[0-0] Bouncer Bot: ${initialMessage}`];
  
      sessionId = session; // Store session ID
  
      const modalWidth = window.innerWidth * 0.9;
      const modalHeight = window.innerHeight * 0.9;
  
      const modalContainer = add([fixed()]);
      const modal = modalContainer.add([
          rect(modalWidth, modalHeight),
          outline(5),
          pos((window.innerWidth - modalWidth) / 2, (window.innerHeight - modalHeight) / 2),
          color(220, 220, 220),
          fixed(),
      ]);
  
      const chatAreaHeight = modalHeight * 0.75;
      const inputAreaHeight = modalHeight * 0.15;
  
      const chatArea = modal.add([
          rect(modalWidth - 20, chatAreaHeight),
          color(255, 255, 255),
          pos(10, 10),
          area(),
          fixed(),
      ]);
  
      // 🟢 Reduce text size to fit more messages
      const messagesDisplay = chatArea.add([
          text("", {
              size: 18, // Reduced from 28 to 18px
              width: modalWidth - 40,
              lineSpacing: 5,
          }),
          color(10, 10, 10),
          pos(10, 10),
          fixed(),
      ]);
  
      const inputBox = modal.add([
          rect(modalWidth - 160, inputAreaHeight),
          color(255, 255, 255),
          pos(10, modalHeight - inputAreaHeight - 10),
          outline(2),
          area(),
          "inputBox",
          fixed(),
      ]);
  
      const inputTextDisplay = inputBox.add([
          text("", {
              size: 18, // Make text input smaller too
              width: modalWidth - 180,
              lineSpacing: 5,
          }),
          color(10, 10, 10),
          pos(10, 10),
          fixed(),
      ]);
  
      const sendButton = modal.add([
          rect(140, inputAreaHeight),
          color(0, 150, 0),
          pos(modalWidth - 150, modalHeight - inputAreaHeight - 10),
          outline(2),
          area(),
          "sendButton",
          fixed(),
      ]);
  
      sendButton.add([
          text("Send", { size: 20 }), // Slightly smaller
          pos(70, inputAreaHeight / 2),
          anchor("center"),
          color(255, 255, 255),
          fixed(),
      ]);
  
      const closeButton = modal.add([
          rect(100, 40),
          color(200, 50, 50),
          pos(modalWidth - 120, 10), // Top-right corner
          outline(2),
          area(),
          "closeButton",
          fixed(),
      ]);
  
      closeButton.add([
          text("Close", { size: 18 }), // Smaller for consistency
          pos(50, 20),
          anchor("center"),
          color(255, 255, 255),
          fixed(),
      ]);
  
      function updateMessages() {
          const maxMessages = Math.floor(chatAreaHeight / 24); // More messages fit now
          const displayMessages = messages.slice(-maxMessages);
          messagesDisplay.text = displayMessages.join("\n");
      }
  
      function sendMessage() {
          if (inputText.trim() !== "" && sessionId) {
              let userMessage = inputText;
              messages.push(`> You: ${userMessage}`);
              inputText = "";
              inputTextDisplay.text = "";
              updateMessages();
  
              fetch(`/chat/${sessionId}`, {
                  method: "POST",
                  headers: {
                      "Content-Type": "application/json",
                  },
                  body: JSON.stringify({ message: userMessage }),
              })
                  .then((response) => response.json())
                  .then((data) => {
                      if (data.response) {
                          messages.push(`[0-0] Bouncer Bot: ${data.response}`);
                          updateMessages();
                      } else {
                          messages.push("⚠️ Error: No response from server.");
                          updateMessages();
                      }
                  })
                  .catch((error) => {
                      console.error("Chat error:", error);
                      messages.push("⚠️ Error sending message.");
                      updateMessages();
                  });
          }
      }
  
      sendButton.onClick(() => {
          sendMessage();
      });
  
      onKeyPress("enter", () => {
          sendMessage();
      });
  
      onKeyPress("backspace", () => {
          inputText = inputText.slice(0, -1);
          inputTextDisplay.text = inputText;
      });
  
      onCharInput((char) => {
          inputText += char;
          inputTextDisplay.text = inputText;
      });
  
      closeButton.onClick(() => {
          if (sessionId) {
              fetch(`/end_bouncer_test/${sessionId}`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
              })
                  .then((response) => response.json())
                  .then((data) => {
                      console.log(data.message);
                  })
                  .catch((error) => console.error("Error ending session:", error));
          }
          destroy(modalContainer);
          player.isInDialogue = false;
          sessionId = null;
      });
  
      onKeyPress("escape", () => {
          closeButton.click();
      });
  
      updateMessages(); // Ensure initial messages are displayed
  }
  
  

    
    function startBouncerConversation() {
        const uuid = "b4d5adfe-1f93-45d0-a26e-0aaf5ca371cb"; // Replace with actual UUID
    
        fetch("/start_bouncer", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uuid }),
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.session_id && data.initial_response) {
                    openChatModal(data.initial_response, data.session_id); // Start chat with session ID
                } else {
                    openChatModal("⚠️ Error: No response from server.", null);
                }
            })
            .catch((error) => {
                console.error("Error:", error);
                openChatModal("⚠️ Error connecting to server.", null);
            });
    }
    
    player.onCollide("door", () => {
        if (!player.isInDialogue) {
            startBouncerConversation();
        }
    });
    

    player.onCollide("npc", () => {
      player.isInDialogue = true;
      const dialogueBoxFixedContainer = add([fixed()]);
      const dialogueBox = dialogueBoxFixedContainer.add([
        rect(1000, 200),
        outline(5),
        pos(150, 500),
        fixed(),
      ]);
      const dialogue =
        "Defeat all monsters on this island and you'll become the champion!";
      const content = dialogueBox.add([
        text("", {
          size: 42,
          width: 900,
          lineSpacing: 15,
        }),
        color(10, 10, 10),
        pos(40, 30),
        fixed(),
      ]);
  
      if (worldState.faintedMons.length < 4) {
        content.text = dialogue;
      } else {
        content.text = "You're the champion!";
      }
  
      onUpdate(() => {
        if (isKeyDown("space")) {
          destroy(dialogueBox);
          player.isInDialogue = false;
        }
      });
    });
  
    function flashScreen() {
      const flash = add([
        rect(window.innerWidth, window.innerHeight),
        color(10, 10, 10),
        fixed(),
        opacity(0),
      ]);
      tween(
        flash.opacity,
        1,
        0.5,
        (val) => (flash.opacity = val),
        easings.easeInBounce
      );
    }
  }
  