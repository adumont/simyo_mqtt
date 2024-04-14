[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

# Simyo to MQTT in Heroku

Pull your Simyo data and publish them to an MQTT broker in Heroku.

## How to update the keys in the script?

There are 3 keys we need to access the Simyo API. On ocasion, Simyo will change them, so the script will stop working. You don't have to do that, usually I will update the script if I see the keys don't work anymore. I just put this here for personal reference.

Here's how to get the new values:

### Method 1 - Frida + Objection

Get the path to the apk in the device:

```
$ adb shell pm path com.simyo
```

Download the APK:

```
$ adb pull /data/app/com.simyo-v348BAJ08KuuJy3xYvCFIA==/base.apk
```

Patch the APK with Frida Gadget using objection (ref: https://blog.netspi.com/four-ways-bypass-android-ssl-verification-certificate-pinning/)

```
$ objection patchapk -s base.apk
```

Uninstall the app from the phone, and install the patch version:

```
$ adb install base.objection.apk
```

If it fails with `INSTALL_FAILED_VERIFICATION_FAILURE` (see [this](https://stackoverflow.com/a/34666037/728281)), run:

```
$ adb shell settings put global verifier_verify_adb_installs 0
```

Sometimes you will need to disable the package verifier as well using:

```
$ adb shell settings put global package_verifier_enable 0
```

Get trace.js from this repository. (adapted from https://github.com/iddoeldor/frida-snippets#trace-class)

Run the patched App on the phone. It will pause until you run objection explore:

Run objection explore (on the linux host)

```
$ objection explore
Using USB device `HUAWEI COL-L29`
Agent injected and responds ok!

     _   _         _   _
 ___| |_|_|___ ___| |_|_|___ ___
| . | . | | -_|  _|  _| | . |   |
|___|___| |___|___|_| |_|___|_|_|
      |___|(object)inject(ion) v1.7.4

     Runtime Mobile Exploration
        by: @leonjza from @sensepost

[tab] for command suggestions
com.simyo on (HONOR: 9)
```

Now, load the trace.js script into `objection`:

```
[usb] # evaluate trace.js
JavaScript capture complete. Evaluating...
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.getKeyDes","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.decryptFromDES","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.encryptToDES","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.getSign","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.getSignWithoutParameter","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.textToHmacSHA256","overloaded":1}
{"tracing":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.validateSign","overloaded":1}
com.simyo on (HONOR: 9) [usb] # 
```

Now we login into the App. At this point, the App will call the hooked methods, `objection` will show log lines like this, revealing the keys:

```
{"#":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.getKeyDes","args":[{"i":0,"o":"TFq2VBDo3BizNAcPEw1vB7i5LfRvOg","s":"TFq2VBDo3BizNAcPEw1vB7i5LfRvOg"}],"returns":{"val":{"$handle":"0x1d79a","$weakRef":28},"str":"[object Object]"}}

{"#":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.encryptToDES","args":[{"i":0,"o":"MYPASSWORDHERE","s":"MYPASSWORDHERE"},{"i":1,"o":"TFq2VBDo3BizNAcPEw1vB7i5LfRvOg","s":"TFq2VBDo3BizNAcPEw1vB7i5LfRvOg"}],"returns":{"val":"ENCRYPTEDPASSWORDHERE","str":"ENCRYPTEDPASSWORDHERE"}}

{"#":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.textToHmacSHA256","args":[{"i":0,"o":"BHqCzYg8BAmZhttps://api.simyo.es/simyo-api/login?publickey=1scopdqvespjtky","s":"BHqCzYg8BAmZhttps://api.simyo.es/simyo-api/login?publickey=1scopdqvespjtky"}],"returns":{"val":"f872b75525d6f4d1eb9e301a682ca560c4c3cf0d8a06f463a0235006c5989dea","str":"f872b75525d6f4d1eb9e301a682ca560c4c3cf0d8a06f463a0235006c5989dea"}}

{"#":"com.simyo.data.network.simyoapi.api.utils.CifradoUtil.getSign","args":[{"i":0,"o":"https://api.simyo.es/simyo-api/login?publicKey=1SCOPDqVeSPjTKy","s":"https://api.simyo.es/simyo-api/login?publicKey=1SCOPDqVeSPjTKy"},{"i":1,"o":null,"s":"null"}],"returns":
{"val":"f872b75525d6f4d1eb9e301a682ca560c4c3cf0d8a06f463a0235006c5989dea","str":"f872b75525d6f4d1eb9e301a682ca560c4c3cf0d8a06f463a0235006c5989dea"}}      
```

From the dump, we'll see:

* The call to getKeyDes() reveals the DES key: "TFq2VBDo3BizNAcPEw1vB7i5LfRvOg". Actually we only need the 24 first characters: "TFq2VBDo3BizNAcPEw1vB7i5"
* The call to textToHmacSHA256() reveals two more keys 
  * the first one is right before the https:// : "BHqCzYg8BAmZ".
  * the second one is the publicKey: "1scopdqvespjtky"

They go there in the script:

```
def getApiSig(url):
   [...]
   dig = hmac.new(b'BHqCzYg8BAmZ', msg='BHqCzYg8BAmZ' + url.lower(), digestmod=hashlib.sha256).digest()
   [...]
```

```
def simyopass():
   [...]
   k = pyDes.triple_des("TFq2VBDo3BizNAcPEw1vB7i5", pyDes.ECB, "\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)
   [...]
```

```
def api_request(url, data="", check=True):
   [...]
   kPublicKey="1SCOPDqVeSPjTKy"
   [...]
```

### Method 2: From the native library

We'll need to extract the APK in the same way we did with method 1. Once we have the APK, we can use apktool to decompile it, using `apktool d base.apk`. 

Using strings will reveal the same three keys (not sure the order is always respected):

```
$ strings base/lib/x86/libnative-lib.so
[...]
libm.so
libdl.so
BHqCzYg8BAmZ
TFq2VBDo3BizNAcPEw1vB7i5LfRvOg
1SCOPDqVeSPjTKy
;*2$"
[...]
```

# Credits for the original script (that I have modified and adapted for my purpose)

poliva
https://github.com/poliva/random-scripts/tree/master/simyo
