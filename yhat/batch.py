import urllib2
import json
import StringIO
import base64
import os
import sys
import os.path
import re
import tarfile
from urlparse import urljoin
from poster.encode import multipart_encode, MultipartParam
from poster.streaminghttp import register_openers
from progressbar import ProgressBar, Percentage, Bar, FileTransferSpeed, ETA

from deployment.save_session import save_function

class BatchJob(object):

    def __init__(self, name, **kwargs):
        if not re.match("^[A-Za-z0-9_]+$", name):
            raise ValueError("job name must container only [A-Za-z0-9_]" \
                    .format(key))
        self.name = name
        for key in ["username", "apikey", "url"]:
            if not key in kwargs:
                raise ValueError("{} not specified".format(key))
            setattr(self, key, kwargs[key])

    def __create_bundle_tar(self, bundle, filename):
        buf = StringIO.StringIO()
        buf.write(bundle)
        buf.seek(0)
        bundle_tarinfo = tarfile.TarInfo("bundle.json")
        bundle_tarinfo.size = len(bundle)

        # make sure old files are gone from previous job
        if os.path.isfile(filename):
            os.remove(filename)

        archive = tarfile.open(filename, "w:gz")
        archive.addfile(tarinfo=bundle_tarinfo, fileobj=buf)
        if os.path.isfile("yhat.yaml"):
            archive.add("yhat.yaml")
        if os.path.isfile("requirements.txt"):
            archive.add("requirements.txt")
        archive.close()

    def __post_file(self, filename, url, username, job_name, apikey):
        register_openers()

        widgets = ["Transferring job data: ", Bar(), Percentage(), " ", \
            ETA(), " ", FileTransferSpeed()]

        progress_bar = ProgressBar(widgets=widgets).start()

        def progress(param, current, total):
            if not param:
                return
            progress_bar.maxval = total
            progress_bar.update(current)

        data = open(filename, "rb")
        form_data = {
            "job": data,
            "job_name": job_name
        }
        datagen, headers = multipart_encode(form_data, cb=progress)

        req = urllib2.Request(url, datagen, headers)

        # Set authentication on request
        auth = "{}:{}".format(username, apikey)
        encoded_auth = base64.encodestring(auth).replace("\n", "")
        req.add_header("Authorization", "Basic {}".format(encoded_auth))
        try:
            response = urllib2.urlopen(req)
        except urllib2.HTTPError, e:
            text = e.read()
            sys.stderr.write("\nServer error: {}".format(text))
            return
        except Exception, e:
            sys.stderr.write("\nError: {}".format(e))
            return
        response_text = response.read()

        progress_bar.finish()

    ##TODO:
    # print out what's going to happen before deploying and confirm
    # if sure, don't confirm
    # Is there some reason you might want to pass in something other than
    #    globals?
    def deploy(self, session, verbose=False):
        # TODO: Is there some reason you might want to pass in something
        # other than globals()??
        bundle = save_function(self.__class__, session, verbose=verbose)
        bundle["class_name"] = self.__class__.__name__
        bundle_str = json.dumps(bundle)
        filename = ".tmp_yhat_job.tar.gz"
        self.__create_bundle_tar(bundle_str, filename)
        url = urljoin(self.url, "/batch/deploy")
        print("posting to", url)
        self.__post_file(filename, url, self.username, self.name, self.apikey)

    def execute(self):
        pass
