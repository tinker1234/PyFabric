"""Test mod for pymods/lib - copy to run/pymods/libdemo/main.py.

Setup (run/pymods/lib/):
  commons-math3-3.6.1.jar                 https://repo1.maven.org/maven2/org/apache/commons/commons-math3/3.6.1/
  sub/mchelper.jar                        a jar compiled against Minecraft (calls BuiltInRegistries)
  tabulate-0.10.0-py3-none-any.whl        pip download --no-deps tabulate
  humanize-*-py3-none-any.whl             pip download --no-deps humanize
  pyyaml-*-cp312-*-win_amd64.whl          must be SKIPPED (native code)
  mypkg/__init__.py                       def greet(n): return f"hi {n} from mypkg"
Then: start the server, check LIB1-LIB6 in the log; /jsouptest fails, drop jsoup-*.jar into
run/pymods/libdemo/lib/, /pyfabric reload, /jsouptest prints "Hello jsoup".
"""
from pyfabric import libs, log, command
import java

Primes = java.type("org.apache.commons.math3.primes.Primes")
McHelper = libs.java("com.example.McHelper")
from tabulate import tabulate
import humanize
import mypkg

log("LIB1", Primes.nextPrime(1000), Primes.isPrime(7919))
log("LIB2", tabulate([["a", 1], ["b", 2]], headers=["k", "v"], tablefmt="plain").replace("\n", " | "))
log("LIB3", humanize.intcomma(1234567), mypkg.greet("Michael"))
log("LIB4", McHelper.diamondId(), McHelper.itemCount() > 1000)
log("LIB5", [p.split("/")[-1] for p in libs.loaded()["jars"]], [s[0].split("/")[-1] for s in libs.loaded()["skipped"]])
try:
    import yaml
    log("LIB6 yaml imported?!")
except ImportError:
    log("LIB6 yaml correctly unavailable")


@command("jsouptest")
def jsouptest(ctx):
    Jsoup = libs.java("org.jsoup.Jsoup")
    ctx.reply(str(Jsoup.parse("<p>Hello <b>jsoup</b></p>").text()))
