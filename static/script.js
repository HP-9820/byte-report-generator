const form = document.getElementById("uploadForm");

form.addEventListener("submit", async function(e) {
    e.preventDefault();
    const formData = new FormData(form);

    // Send the file to upload endpoint
    await fetch("/upload", {
        method: "POST",
        body: formData
    });

    // Start checking status
    checkStatus();
});

async function checkStatus() {
    const res = await fetch("/status");
    const data = await res.json();

    // Update progress bar
    document.getElementById("progressBar").style.width = data.progress + "%";
    document.getElementById("progressText").innerText = data.progress + "%";

    // Show current student being processed
    if(data.current) {
        document.getElementById("statusText").innerText =
            data.current + " report is generating... please wait";
    }

    // Update report list
    const list = document.getElementById("reportList");
    list.innerHTML = "";
    data.reports.forEach(report => {
        const link = document.createElement("a");
        link.href = "/download/" + report.file;
        link.innerText = report.name;
        list.appendChild(link);
        list.appendChild(document.createElement("br"));
    });

    if(data.progress < 100) {
        setTimeout(checkStatus, 2000);
    } else {
        document.getElementById("statusText").innerText =
            "All reports generated successfully";
    }
}