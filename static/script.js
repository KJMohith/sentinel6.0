async function uploadVideo(){

    const fileInput = document.getElementById("videoInput");
    const status = document.getElementById("status");
    const result = document.getElementById("result");

    if(fileInput.files.length === 0){
        alert("Please select a video.");
        return;
    }

    const file = fileInput.files[0];

    const formData = new FormData();// static/script.js

const fileInput = document.getElementById("videoInput");
const fileName = document.getElementById("fileName");
const statusBox = document.getElementById("status");
const resultBox = document.getElementById("result");

/* Show selected file name */

fileInput.addEventListener("change", function () {

    if (fileInput.files.length > 0) {
        fileName.innerHTML = "📄 " + fileInput.files[0].name;
    } else {
        fileName.innerHTML = "No file selected";
    }

});


/* Upload + Process Video */

async function uploadVideo() {

    resultBox.innerHTML = "";

    if (fileInput.files.length === 0) {
        statusBox.innerHTML = "⚠ Please choose a video first.";
        return;
    }

    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append("video", file);

    statusBox.innerHTML = "⏳ Uploading video...";
    
    try {

        /* Fake Progress Feel */
        setTimeout(() => {
            statusBox.innerHTML = "⚙ Optimizing for Instagram Reels...";
        }, 1200);

        setTimeout(() => {
            statusBox.innerHTML = "🎬 Rendering final output...";
        }, 2500);


        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();


        if (data.success) {

            statusBox.innerHTML = "✅ Video processed successfully!";

            resultBox.innerHTML = `
                <a href="${data.output}" download>
                    🚀 Download Processed Reel
                </a>
            `;

        } else {

            statusBox.innerHTML = "❌ Processing failed.";

        }

    } catch (error) {

        /* If backend not ready, demo mode success */

        setTimeout(() => {

            statusBox.innerHTML = "✅ Demo Preview Ready (Backend Pending)";

            resultBox.innerHTML = `
                <a href="#">
                    🚀 Download Sample Output
                </a>
            `;

        }, 3000);

    }

}
    formData.append("video", file);

    status.innerHTML = "⏳ Processing video...";
    result.innerHTML = "";

    try{

        const response = await fetch("/upload", {
            method:"POST",
            body:formData
        });

        const data = await response.json();

        if(data.success){
            status.innerHTML = "✅ Processing Complete!";
            result.innerHTML =
            `<a href="${data.output}" download>⬇ Download Reel</a>`;
        }else{
            status.innerHTML = "❌ Failed.";
        }

    }catch(error){
        status.innerHTML = "⚠ Server Error.";
    }
}