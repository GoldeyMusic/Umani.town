/* #TODO
Pedro made this smarter(Ai sayd: but it's still a bit too long.)
*/
WA.onInit().then(async () => {
  function handleRoofVisibility(layerName) {
    WA.room.area.onEnter(`roof_${layerName}`).subscribe(() => WA.room.hideLayer(`roofs/${layerName}`));
    WA.room.area.onLeave(`roof_${layerName}`).subscribe(() => WA.room.showLayer(`roofs/${layerName}`));
  }

  const roofLayers = ["lowerLeft", "lowerRight", "upperLeft", "upperRight", "sacem"];

  roofLayers.forEach(layerName => handleRoofVisibility(layerName));
});

// Function to send player data to the webhook
WA.onInit().then(async () => {
  /* #TODO
    This if statement adds unnecessary nesting.
    It should be refactored into the oposite condition, with a return statement to stop the function execution
    */
  if (!WA.player.tags.includes("bot")) {
    /* #TODO
    Declaring your function sendPlayerData inside of this IF statement, makes reading the code unnecessarily complicated.
    It can be declared somewhere else and used in this context. Making the if statement's intentions more explicit.
    By declaring this big function in this scope you're mixing your "behaviour declaration" with the control-flow logic without any real benefit.
    */
    async function sendPlayerData(
      firstPing = false,

      
    ) {
      const WEBHOOK_URL = "https://apps.taskmagic.com/api/v1/webhooks/udowzdkJjQ2MJUNTpL1A0";
      /* #TODO
        Try catch when used like this isn't an anti-pattern, but could be made cleaner with promise chaining.
        (PROMISE.THEN(RES=>RES.JSON()).CATCH(E))
        */
      try {
        /* #TODO
        This code is already run inside of WA.onInit() on line 43.
        In theory you shouldn't need to await or call WA.onInit() in here again.
        */
        await WA.onInit();
        /* #TODO
          could be cleaner with object desctructuring syntax
          `const {id,name} = WA.player`
          especially because you're using `const payload = {id,name,firstPing}`  , later
         */
        const playerId = WA.player.id;
        const playerName = WA.player.name;
        console.log(playerName); // or use the playerName variable elsewhere in your code

        if (!playerId || !playerName) {
          throw new Error("Invalid player data");
        }

        // Create the payload
        const payload = {
          id: playerId,
          name: playerName,
          firstPing: firstPing,
        };

        /* #TODO
        This function has no dependencies and is only a helper function
        it doesn't HAVE to be declared inside of this scope / execution context
        moving it outside, would make the code cleaner / more focused
        */
        // Function to handle fetch with timeout
        const fetchWithTimeout = (url, options, timeout = 5000) => {
          return Promise.race([
            fetch(url, options),
            new Promise((_, reject) =>
              setTimeout(() => reject(new Error("Request timed out")), timeout)
            ),
          ]);
        };

        // Send the payload to the webhook
        const response = await fetchWithTimeout(WEBHOOK_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        /* #TODO
        This !response.ok and await response.json could be simpler,
        if you used promise chaining as in (PROMISE.THEN(RES=>RES.JSON()).CATCH(E))
        */
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("Success:", data);
      } catch (error) {
        console.error("Error:", error);
      }
    }

    /* #TODO
    This firstPing parameter seems a little overly complicated. Is it really necessary?
    Maybe this could be simpler. What are you trying to achieve
    */
    let firstPing = true;

    /* #TODO
    because the parameter is already named in the function true or false could be used directly in here.
    */
    // Call the function to send player data initially with firstPing=true
    sendPlayerData(firstPing);

    // Set firstPing to false after the initial call
    firstPing = false;

    // Call the function every 60 seconds with firstPing=false
    setInterval(() => {
      sendPlayerData(firstPing);
    }, 60000);
  }
});
////////////////////////////////////////////////
WA.onInit().then(() => {
  /* #TODO
    Once again, same behaviour, different parameters (color and "playerCategory")
    could be a reused function, to avoid code repetition.
    */
  if (WA.player.tags.includes("admin")) {
    WA.player.setOutlineColor(128, 0, 128); // Lila
  } else if (WA.player.tags.includes("teacher")) {
    WA.player.setOutlineColor(0, 0, 255); // Blau
  } else if (WA.player.tags.includes("masterclass")) {
    WA.player.setOutlineColor(255, 255, 0); // Gelb
  }
});

